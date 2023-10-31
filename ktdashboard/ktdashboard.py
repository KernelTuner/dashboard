#!/usr/bin/env python
import json
import sys
import os

import panel as pn
import panel.widgets as pnw
import pandas as pd
import bokeh.palettes
from bokeh.models.ranges import FactorRange
from bokeh.transform import jitter
from bokeh.models import HoverTool, LinearColorMapper, CategoricalColorMapper
from bokeh.plotting import ColumnDataSource, figure


class KTdashboard:
    """ Main object to instantiate to hold everything related to a running dashboard"""

    def __init__(self, cache_file, demo=False, default_key=None):
        self.demo = demo
        self.cache_file = cache_file

        # read in the cachefile
        self.cache_file_handle = open(cache_file, "r")
        filestr = self.cache_file_handle.read().strip()
        # if file was not properly closed, pretend it was properly closed
        if not filestr[-3:] == "}\n}":
            # remove the trailing comma if any, and append closing brackets
            if filestr[-1] == ",":
                filestr = filestr[:-1]
            filestr = filestr + "}\n}"

        cached_data = json.loads(filestr)
        self.kernel_name = cached_data["kernel_name"]
        self.device_name = cached_data["device_name"]
        if "objective" in cached_data:
            self.objective = cached_data["objective"]
        else:
            self.objective = "time"

        # get the performance data
        data = list(cached_data["cache"].values())
        data = [d for d in data if d[self.objective] != 1e20 and not isinstance(d[self.objective], str)]

        # use all data or just the first 1000 records in demo mode
        self.index = len(data)
        if self.demo:
            self.index = min(len(data), 1000)

        all_tune_param_keys = cached_data["tune_params_keys"]
        all_tune_params = dict()

        for key in all_tune_param_keys:
            values = cached_data["tune_params"][key]
            for row in data:
                if row[key] not in values:
                    values = sorted(values + [row[key]])

            all_tune_params[key] = values

        # figure out which keys are interesting
        single_value_tune_param_keys = [key for key in all_tune_param_keys if len(all_tune_params[key]) == 1]
        tune_param_keys = [key for key in all_tune_param_keys if key not in single_value_tune_param_keys]
        scalar_value_keys = [key for key in data[0].keys() if not isinstance(data[0][key],list) and key not in single_value_tune_param_keys]
        output_keys = [key for key in scalar_value_keys if key not in tune_param_keys]
        float_keys = [key for key in output_keys if isinstance(data[0][key], float)]

        self.single_value_tune_param_keys = single_value_tune_param_keys
        self.tune_param_keys = tune_param_keys
        self.scalar_value_keys = scalar_value_keys
        self.output_keys = output_keys
        self.float_keys = float_keys

        # Convert to a data frame
        data_df = pd.DataFrame(data[:self.index])[scalar_value_keys]

        # Replace all column that are objects by categorical
        for column, dtype in data_df.dtypes.items():
            if column in tune_param_keys and dtype == "object":
                data_df[column] = pd.Categorical(
                        data_df[column],
                        categories=all_tune_params[column],
                        ordered=True)

        self.data = data
        self.data_df = data_df
        self.source = ColumnDataSource(data=self.data_df)

        plot_options=dict(height=600, width=900)
        plot_options['tools'] = [HoverTool(tooltips=[(k, "@{"+k+"}" + ("{0.00}" if k in float_keys else "")) for k in scalar_value_keys]), "box_select,box_zoom,save,reset"]

        self.plot_options = plot_options

        # find default key
        if default_key is None:
            default_key = 'GFLOP/s'
            if default_key not in scalar_value_keys:
                default_key = 'time'  # Check if time is defined

                if default_key not in scalar_value_keys:
                    default_key = scalar_value_keys[0]

        # setup widgets
        self.yvariable = pnw.Select(name='Y', value=default_key, options=scalar_value_keys)
        self.xvariable = pnw.Select(name='X', value='index', options=['index']+scalar_value_keys)
        self.colorvariable = pnw.Select(name='Color By', value=default_key, options=scalar_value_keys)
        self.xscale = pnw.RadioButtonGroup(name="xscale", options=["linear", "log"])
        self.yscale = pnw.RadioButtonGroup(name="yscale", options=["linear", "log"])

        # connect widgets with the function that draws the scatter plot
        self.scatter = pn.bind(
                self.make_scatter,
                xvariable=self.xvariable,
                yvariable=self.yvariable,
                color_by=self.colorvariable,
                xscale=self.xscale,
                yscale=self.yscale)

        # actually build up the dashboard
        self.dashboard = pn.template.BootstrapTemplate(title='Kernel Tuner Dashboard')
        self.dashboard.main.append(self.scatter)
        self.dashboard.sidebar.append(pn.Column(
            self.yvariable,
            self.xvariable,
            self.colorvariable))

        self.dashboard.sidebar.append(pn.layout.Divider())

        self.dashboard.sidebar.append(pn.Row(
            pn.pane.Markdown("X axis"),
            self.xscale
        ))

        self.dashboard.sidebar.append(pn.Row(
            pn.pane.Markdown("Y axis"),
            self.yscale
        ))

        self.dashboard.sidebar.append(pn.layout.Divider())

        self.multi_choice = list()
        for tune_param in self.tune_param_keys:
            values = all_tune_params[tune_param]

            multi_choice = pnw.MultiChoice(name=tune_param, value=values, options=values)
            self.dashboard.sidebar.append(multi_choice)

            row = pn.bind(self.update_data_selection, tune_param, multi_choice)
            self.dashboard.sidebar.append(row)

    def __del__(self):
        self.cache_file_handle.close()

    def notebook(self):
        """ Return a static version of the dashboard without the template """
        return pn.Row(pn.Column(self.yvariable, self.xvariable, self.colorvariable), self.scatter)

    def update_data_selection(self, tune_param, multi_choice):
        selection_key = tune_param
        selection_values = multi_choice

        mask = self.data_df[selection_key].isin(selection_values)
        index = self.data_df.index[mask].values
        self.index = index

        data_df = self.data_df[mask]
        self.source.data = data_df

    def update_colors(self, color_by):
        dtype = self.data_df.dtypes[color_by]

        if dtype == "category":
            factors = dtype.categories
            if len(factors) < 10:
                palette = bokeh.palettes.Category10[10]
            else:
                palette = bokeh.palettes.Category20[20]


            color_mapper = CategoricalColorMapper(palette=palette, factors=factors)

        else:
            color_mapper = LinearColorMapper(palette='Viridis256', low=min(self.data_df[color_by]),
                                             high=max(self.data_df[color_by]))

        color = {'field': color_by, 'transform': color_mapper}
        return color

    def make_scatter(self, xvariable, yvariable, color_by, xscale, yscale):
        color = self.update_colors(color_by)

        x = xvariable
        y = yvariable

        plot_options = dict(self.plot_options)
        plot_options["x_axis_type"] = xscale
        plot_options["y_axis_type"] = yscale

        # For categorical data, we add some jitter
        dtype = self.data_df.dtypes.get(xvariable)
        if dtype == "category":
            plot_options["x_range"] = list(dtype.categories)
            x = jitter(xvariable, width=0.02, distribution="normal",
                       range=FactorRange(*dtype.categories))

        dtype = self.data_df.dtypes.get(yvariable)
        if dtype == "category":
            plot_options["y_range"] = list(dtype.categories)
            x = jitter(yvariable, width=0.02, distribution="normal",
                       range=FactorRange(*dtype.categories))

        f = figure(**plot_options)
        f.scatter(x, y, size=5, color=color, alpha=0.5, source=self.source)
        f.xaxis.axis_label = xvariable
        f.yaxis.axis_label = yvariable

        pane = pn.Column(pn.pane.Markdown(f"## Auto-tuning {self.kernel_name} on {self.device_name}"), pn.pane.Bokeh(f))

        return pane

    def update_plot(self, i):
        stream_dict = {k:[v] for k,v in dict(self.data[i], index=i).items() if k in ['index']+self.scalar_value_keys}
        self.source.stream(stream_dict)

    def update_data(self):
        if not self.demo:
            new_contents = self.cache_file_handle.read().strip()
            if new_contents:

                # process new contents (parse as JSON, make into dict that goes into source.stream)
                new_contents_json = "{" + new_contents[:-1] + "}"
                new_data = list(json.loads(new_contents_json).values())

                for i,element in enumerate(new_data):

                    stream_dict = {k:[v] for k,v in dict(element, index=self.index+i).items() if k in ['index']+self.scalar_value_keys}
                    self.source.stream(stream_dict)

                self.index += len(new_data)

        if self.demo:
            if self.index < (len(self.data)-1):
                self.update_plot(self.index)
                self.index += 1



def print_usage():
    print("Usage: ./dashboard.py [-demo] filename")
    print("   -demo      option to enable demo mode that mimicks a running Kernel Tuner session")
    print("   filename   name of the cachefile")
    exit(0)



def cli():
    """ implements the command-line interface to start the dashboard """

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

    db = KTdashboard(filename, demo=demo)

    db.dashboard.servable()

    def dashboard_f():
        """ wrapper function to add the callback, doesn't work without this construct """
        pn.state.add_periodic_callback(db.update_data, 1000)
        return db.dashboard
    server = pn.serve(dashboard_f, show=False)



if __name__ == "__main__":
    cli()
