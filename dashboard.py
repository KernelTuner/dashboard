#!/usr/bin/env python
import os
import sys

from functools import partial

import panel as pn
import panel.widgets as pnw
import pandas as pd
import bokeh


from bokeh.plotting import ColumnDataSource
from bokeh.models import HoverTool
from bokeh.layouts import gridplot
from bokeh.plotting import figure, output_notebook, show
from bokeh.models import LinearColorMapper

from kernel_tuner.util import read_cache

cache_last_modified = None



def create_dashboard(cache_file, demo=False):

    #read in the cachefile
    cache_last_modified = os.stat(cache_file).st_mtime
    cached_data = read_cache(cache_file, open_cache=False)
    data = list(cached_data["cache"].values())
    data = [d for d in data if d["time"] != 1e20]

    index = len(data)
    if demo:
        index = 1000

    #figure out which keys are interesting
    single_value_tune_param_keys = [key for key in cached_data["tune_params_keys"] if len(cached_data["tune_params"][key]) == 1]
    tune_param_keys = [key for key in cached_data["tune_params_keys"] if key not in single_value_tune_param_keys]
    single_value_keys = [key for key in data[0].keys() if not isinstance(data[0][key],list) and key not in single_value_tune_param_keys]
    output_keys = [key for key in single_value_keys if key not in tune_param_keys]
    float_keys = [key for key in output_keys if isinstance(data[0][key], float)]


    data_df = pd.DataFrame(data[:index])[single_value_keys]
    source = ColumnDataSource(data=data_df)


    #create selectors
    yvariable  = pnw.Select(name='Y', value='GFLOP/s',
                            options=single_value_keys)
    xvariable  = pnw.Select(name='X', value='index',
                            options=['index']+single_value_keys)
    colorvariable  = pnw.Select(name='Color By', value='GFLOP/s',
                            options=single_value_keys)



    def update_colors(color_by):
        color_mapper = LinearColorMapper(palette='Viridis256', low=min(data_df[color_by]), high=max(data_df[color_by]))
        color = {'field': color_by, 'transform': color_mapper}
        return color



    @pn.depends(xvariable, yvariable, colorvariable)
    def make_scatter(xvariable, yvariable, color_by):

        color = update_colors(color_by)

        plot_options=dict(plot_height=600, plot_width=900)
        plot_options['tools'] = [HoverTool(tooltips=[(k, "@{"+k+"}" + ("{0.00}" if k in float_keys else "")) for k in single_value_keys]), "box_select,box_zoom,save,reset"]

        x = xvariable
        y = yvariable

        f = figure(**plot_options)
        f.circle(x, y, size=5, color=color, alpha=0.5, source=source)
        f.xaxis.axis_label = x
        f.yaxis.axis_label = y

        pane = pn.pane.Bokeh(f)
        return pane

    plot = make_scatter

    dashboard = pn.template.VanillaTemplate(title='Kernel Tuner Dashboard')
    dashboard.sidebar.append(yvariable)
    dashboard.sidebar.append(xvariable)
    dashboard.sidebar.append(colorvariable)

    dashboard.main.append(plot)

    dashboard.servable();



    def update_plot(i):
        nonlocal data, source

        print(f"update_plot called i={i}")

        stream_dict = {k:[v] for k,v in dict(data[i], index=i).items() if k in ['index']+single_value_keys}
        source.stream(stream_dict)


    def update_data():

        print("update_data called")
        nonlocal data, index, source, cache_file

        if os.stat(cache_file).st_mtime > cache_last_modified:
            cached_data = read_cache(cache_file, open_cache=False)

            data = list(cached_data["cache"].values())
            data = [d for d in data if d["time"] != 1e20]

            #stream the data that has not been streamed yet
            source.stream(pd.DataFrame([data[index:]])) #this may not work, we might need to convert it into a dict like in update_plot
            index = len(data)

        if demo:

            if index < len(data)-1:
                update_plot(index)
                index += 1


    def dashboard_f():
        pn.state.add_periodic_callback(update_data, 1000)
        return dashboard

    server = pn.serve(dashboard_f)




def print_usage():
    print("Usage: ./dashboard.py [-demo] filename")
    print("   -demo      option to enable demo mode that mimicks a running Kernel Tuner session")
    print("   filename   name of the cachefile")
    exit(0)




if __name__ == "__main__":

    if len(sys.argv) < 2:
        print_usage()

    filename = ""
    demo = False
    if len(sys.argv) == 2:
        if os.path.isfile(sys.argv[1]):
            filename = sys.argv[1]
        else:
            print("Cachefile not found")
            exit(1)
    elif len(sys.argv) == 3:
        if sys.argv[1] == "-demo":
            demo = True
        else:
            print_usage()
        if os.path.isfile(sys.argv[2]):
            filename = sys.argv[2]

    create_dashboard(filename, demo)

