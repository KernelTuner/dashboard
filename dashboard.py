import os
from kernel_tuner import read_cache # actually kernel_tuner.util read_cache

import panel as pn
import panel.widgets as pnw
import pandas as pd
from bokeh.models import HoverTool, LinearColorMapper
from bokeh.plotting import ColumnDataSource, figure
pn.extension()


class KTdashboard:
    """ Main object to instantiate to hold everything related to a running dashboard"""

    def __init__(self, cache_file, demo=False):
        self.demo = demo
        self.cache_file = cache_file
        # read in the cachefile
        self.cache_last_modified = os.stat(cache_file).st_mtime
        cached_data = read_cache(cache_file, open_cache=False)
        self.kernel_name = cached_data["kernel_name"]
        self.device_name = cached_data["device_name"]

        # get the performance data
        data = list(cached_data["cache"].values())
        data = [d for d in data if d["time"] != 1e20]

        # use all data or just the first 1000 in demo mode
        self.index = len(data)
        if self.demo:
            self.index = 1000

        # figure out which keys are interesting
        single_value_tune_param_keys = [key for key in cached_data["tune_params_keys"] if len(cached_data["tune_params"][key]) == 1]
        tune_param_keys = [key for key in cached_data["tune_params_keys"] if key not in single_value_tune_param_keys]
        single_value_keys = [key for key in data[0].keys() if not isinstance(data[0][key],list) and key not in single_value_tune_param_keys]
        output_keys = [key for key in single_value_keys if key not in tune_param_keys]
        float_keys = [key for key in output_keys if isinstance(data[0][key], float)]

        self.single_value_tune_param_keys = single_value_tune_param_keys
        self.tune_param_keys = tune_param_keys
        self.single_value_keys = single_value_keys
        self.output_keys = output_keys
        self.float_keys = float_keys

        self.data_df = pd.DataFrame(data[:self.index])[single_value_keys]
        self.source = ColumnDataSource(data=self.data_df)
        self.data = data

        plot_options=dict(plot_height=600, plot_width=900)
        plot_options['tools'] = [HoverTool(tooltips=[(k, "@{"+k+"}" + ("{0.00}" if k in float_keys else "")) for k in single_value_keys]), "box_select,box_zoom,save,reset"]

        self.plot_options = plot_options

        # setup widgets
        self.yvariable = pnw.Select(name='Y', value='GFLOP/s', options=single_value_keys)
        self.xvariable = pnw.Select(name='X', value='index', options=['index']+single_value_keys)
        self.colorvariable = pnw.Select(name='Color By', value='GFLOP/s', options=single_value_keys)

        self.scatter = pn.bind(self.make_scatter, xvariable=self.xvariable, yvariable=self.yvariable, color_by=self.colorvariable)

        self.dashboard = pn.template.BootstrapTemplate(title='Kernel Tuner Dashboard')
        self.dashboard.sidebar.append(pn.Column(self.yvariable, self.xvariable, self.colorvariable))
        self.dashboard.main.append(self.scatter)
        self.dashboard.servable()

    def update_colors(self, color_by):
        color_mapper = LinearColorMapper(palette='Viridis256', low=min(self.data_df[color_by]),
                                         high=max(self.data_df[color_by]))
        color = {'field': color_by, 'transform': color_mapper}
        return color

    def make_scatter(self, xvariable, yvariable, color_by):

        color = self.update_colors(color_by)

        x = xvariable
        y = yvariable

        f = figure(**self.plot_options)
        f.circle(x, y, size=5, color=color, alpha=0.5, source=self.source)
        f.xaxis.axis_label = x
        f.yaxis.axis_label = y

        pane = pn.Column(pn.pane.Markdown(f"## Auto-tuning {self.kernel_name} on {self.device_name}"), pn.pane.Bokeh(f))

        return pane

    def update_plot(self, i):
        stream_dict = {k:[v] for k,v in dict(self.data[i], index=i).items() if k in ['index']+self.single_value_keys}
        self.source.stream(stream_dict)

    def update_data(self):
        if os.stat(self.cache_file).st_mtime > self.cache_last_modified:
            cached_data = read_cache(self.cache_file, open_cache=False)

            data = list(cached_data["cache"].values())
            data = [d for d in data if d["time"] != 1e20]

            # stream the data that has not been streamed yet
            self.source.stream(pd.DataFrame([data[self.index:]])) # this may not work, we might need to convert it into a dict like in update_plot
            self.index = len(self.data)
        if self.demo:
            if self.index < (len(self.data)-1):
                self.update_plot(self.index)
                self.index += 1



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


    db = KTdashboard(filename, demo=demo)

    def dashboard_f():
        pn.state.add_periodic_callback(db.update_data, 1000)
        return db.dashboard

    server = pn.serve(dashboard_f)
