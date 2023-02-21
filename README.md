# README #

This module simplifies reading and writing SAMOS netcdf files using xarray.

### Dependencies ###
* Python modules
    * xarray
    * metpy (only required for samosxarray_demo.py, but is useful for automatically applying units to data)
* Command-line tools
    * NCO (https://nco.sourceforge.net/) - Note that this is only required to write .nc files if you want to remove the extra "string1" dimension that gets added by xarray because of how it handles char arrays in NETCDF3_CLASSIC files. You can opt not to do this and therefore not require NCO by setting the fix_dims argument to False when calling to_samos_netcdf().

### How do I get set up? ###

* Clone this repository in the directory with your Python code with
    git clone git@bitbucket.org:coaps_mdc/samosxarray.git
* Import samosxarray in your code file, (note this is assuming samosxarray.py is in a directory called samosxarray):
    import samosxarray.samosxarray as sx
* See samosxarray_demo.py for examples of reading a SAMOS .nc, making calculations, changing flag values, writing a SAMOS .nc.

### Who do I talk to? ###

* Marc Castells (mcastells@coaps.fsu.edu)