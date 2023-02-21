import logging
import string
import subprocess
import numpy as np
import xarray as xr

def pint_units(ds: xr.Dataset) -> xr.Dataset:
    units = {
        'lat': 'degree',
        'lon': 'degree',
        'DIR': 'degree',
        'PL_HD': 'degree',
        'PL_CRS': 'degree',
        'PL_WDIR': 'degree',
        'SSPS': 'g kg-1' # PSU to g/kg
    }
    for var_name, da in ds.items():
        if da.dims==('time',) and var_name.rstrip(string.digits) in units.keys():
            ds[var_name].attrs['units'] = units[var_name.rstrip(string.digits)]

    return ds

def update_flag(ds: xr.Dataset, var_name: str, index: int, new_flag_value: bytes):
    # this seems to be the only way to update the value of a flag
    flags_copy = ds.flag.data
    flags_copy[index, int(ds[var_name].qcindex)-1] = new_flag_value
    ds.flag.data = flags_copy

    return ds

def fix_rh_b_flags(ds: xr.Dataset) -> xr.Dataset:
    for var_name in [var_name for var_name, da in ds.items() if var_name.startswith('RH') and da.dims == ('time',)]:
        var_flags = get_var_flags(ds, var_name)
        b_flag_indices = np.where(var_flags.data == b'B')[0]

        for index in b_flag_indices:
            if ds[var_name].data[index] > 100.0:
                ds[var_name].data[index] = 100.0
                ds = update_flag(ds, var_name, index, b'Z')
    
    return ds


def nan_flags(ds: xr.Dataset, good_flags: list = None, bad_flags: list = None) -> xr.Dataset:
    if good_flags and bad_flags:
        raise Exception('Must choose "good_flags" or "bad_flags", but not both.')
    if not good_flags and not bad_flags:
        good_flags = ['Z']

    for var_name in [var_name for var_name, da in ds.items() if da.dims == ('time',)]:
        
        nan_indices = np.where(np.isnan(ds[var_name].data))[0]
        flags = get_var_flags(ds, var_name)

        # if value is NaN (because the value in .nc file is equal to "missing_value" or "special_value"), but flag is Z, set flag to J (erroneous)
        for index in nan_indices:
            if flags.data[index] == b'Z':
                ds = update_flag(ds, var_name, index, b'J')
        
        if good_flags:
            for i, flag in enumerate(flags.data):
                if flag.decode() not in good_flags:
                    ds[var_name].data[i] = np.nan
        elif bad_flags:
            ds.bad_flags = bad_flags
            for i, flag in enumerate(flags):
                if flag.decode() in bad_flags:
                    ds[var_name].data[i] = np.nan

    return ds

def flag_summary(ds: xr.Dataset) -> str:
    output = '\nSAMOS flags:'

    for var_name, da in ds.items():
        if da.dims==('time',) and hasattr(da, 'units'):
            output += f'\n    {var_name} ({da.attrs["units"]}) [{da.attrs["long_name"]} ({da.attrs["original_units"]})]'
            flags, flag_counts = np.unique(get_var_flags(ds,var_name).data, return_counts=True)
            for flag, flag_count in zip(flags, flag_counts):
                output += f'\n        {flag.decode()}'
                try:
                    output += f' ({ds.flag.attrs[flag.decode()]})'
                except AttributeError as err:
                    logging.warning(err)
                output += f': {flag_count} ({100*flag_count/ds.time.size:.1f}%)'

    return output

def get_var_flags(ds: xr.Dataset, var_name) -> xr.DataArray:
    return ds['flag'].sel(f_string=ds[var_name].qcindex)

def to_samos_netcdf(ds: xr.Dataset, filepath, format = 'NETCDF3_CLASSIC', time_units = 'minutes since 1980-1-1 0:0:0', fix_dims = True, **kwargs):
    encoding = {
        'time': {'units': time_units}
    }

    for nc_var in ds.keys():
        encoding[nc_var] = {'_FillValue': None}


    ds.to_netcdf(filepath, encoding=encoding, format=format, **kwargs)

    if fix_dims:
        # the following commands require NCO to be installed
        # https://nco.sourceforge.net/nco.html

        # this command removes the string1 dimension that xarray adds to the file by "averaging over it"
        ncwa_command = f'ncwa -O -C -a string1 {filepath} {filepath}'
        
        # this command removes the cell_methods attribute that is created when "averaging over" the string1 dimension
        ncatted_command = f'ncatted -a cell_methods,flag,d,, -a cell_methods,history,d,, {filepath}'
        
        logging.info(ncwa_command)
        result = subprocess.run(ncwa_command, shell=True, capture_output=True)

        if result.stderr != b'':
            error = f"{result.args} {result.stdout.decode('utf-8')} {result.stderr.decode('utf-8')}"
            logging.error(error)
            raise Exception(error)

        logging.info(ncatted_command)
        result = subprocess.run(ncatted_command, shell=True, capture_output=True)

        if result.stderr != b'':
            error = f"{result.args} {result.stdout.decode('utf-8')} {result.stderr.decode('utf-8')}"
            logging.error(error)
            raise Exception(error)

def open_dataset(filepath, good_flags: list = None, bad_flags: list = None, fix_rh_over_100: bool = True) -> xr.Dataset:
    '''
    Returns xarray Dataset where the values in each DataArray are set to np.nan based on the lists
    of good_flags or bad_flags provided. If no list of flags are provided, this array only contains
    values flagged as "Z", which means "good data".
    
    Additionally, the time variable is converted to datetime64 and the flag variable of the Dataset
    object is properly formatted as a 2-D array, with the f_string coordinate values using 1-based
    indexing to match the qcindex attribute of the data variables. This allows for using the .sel()
    method directly with the qcindex attribute value of a variable to get a flag array for that variable.
    
    e.g., ds['flag'].sel(f_string=ds['T'].qcindex)

    This is simplified with the get_flags(var_name) method.

    e.g., samosxarray.get_flags(ds, 'T')
    '''

    # concat_characters=False is required to prevent the 2D flag array being flattened to a 1D array by
    # concatting all of the flags for each timestep into 1 string.
    # from xarray docs: concat_characters (bool, optional) – If True, concatenate along the last dimension of character arrays to form string arrays. Dimensions will only be concatenated over (and removed) if they have no corresponding variable and if they are only used as the last dimension of character arrays. This keyword may not be supported by all the backends.
    ds = xr.open_dataset(filepath, concat_characters=False, decode_cf=True, drop_variables=['date','time_of_day'])
        
    # adding 1 to f_string coords because qcindex attribute uses 1-based indexing.
    # this allows the value of the qcindex attribute to be used in the .sel() method.
    # e.g., ds['flag'].sel(f_string=ds['T'].qcindex)
    ds = ds.assign_coords(f_string=np.arange(ds.dims['f_string'])+1)

    # set units to strings parsable by pint/metpy where possible.
    ds = pint_units(ds)

    # if RH is over 100 and flag is set to B, set RH to 100 and set flag to Z
    if fix_rh_over_100:
        ds = fix_rh_b_flags(ds)

    # set the values of each DataArray to np.nan where they correspond to "bad flags"
    ds = nan_flags(ds, good_flags, bad_flags)

    return ds

if __name__ == '__main__':
    filepath = 'WCX7445_20111009v30001.nc'
    
    print(f'Opening {filepath}')

    ds = open_dataset(filepath)

    print(ds)

    print(flag_summary(ds))