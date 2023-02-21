import os
import samosxarray as sx
import metpy.calc as mpcalc
import matplotlib.pyplot as plt

if __name__ == '__main__':
    filepath = 'WCX7445_20111009v30001.nc'
    
    print(f'Opening {filepath}')

    ds = sx.open_dataset(filepath)

    print(ds)
    print(sx.flag_summary(ds))

    dewpoint = mpcalc.dewpoint_from_relative_humidity(temperature=ds['T'].metpy.quantify(), relative_humidity=ds['RH'].metpy.quantify())
     
    print(f"{dewpoint = }")

    fig, ax1 = plt.subplots()
    fig.suptitle(ds.title)

    ax1.set_ylabel(ds['T'].units)

    ax2 = ax1.twinx()
    ax2.set_ylabel(ds['RH'].units)
    ax2.set_ylim(0, 100.5)

    t_plot, = ax1.plot(ds.time, ds['T'], label=ds['T'].long_name)
    rh_plot, = ax2.plot(ds.time, ds['RH'], c='green', label=ds['RH'].long_name)
    dewpoint_plot, = ax1.plot(ds.time, dewpoint, label='dewpoint')
    
    ax1.legend([t_plot, dewpoint_plot, rh_plot], [t_plot.get_label(), dewpoint_plot.get_label(), rh_plot.get_label()])

    plt.show()

    # test setting flags
    for index in range(100,200):
        ds = sx.update_flag(ds, 'SSPS', index, b'K')

    sx.to_samos_netcdf(ds, 'demo.nc')

    ds.close()

    ds = sx.open_dataset('demo.nc')

    print(ds)
    print(sx.flag_summary(ds))

    ds.close()

    os.remove('demo.nc')