import glob
import os.path
import tkinter as tk
from tkinter import ttk

# Matplotlib configuration and imports grouped together
import matplotlib
from fuzzywuzzy import process

matplotlib.use("TkAgg")
import tkinter as tk
from tkinter import ttk
from typing import Any, Tuple

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

# Imports from custom modules grouped together
from gui.tailer import *
from gui.tsfile import *
from gui.util import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# ----------------------------------------------------------------------
#
#  BASE PANEL CLASS
#

# A "panel" is a page in the notebook part of the cTOASTER GUI,
# displaying a particular type of information about a job.  There are
# a number of different panel classes derived from the base class
# here.  Each panel is created as a single Ttk frame and added to the
# notebook -- the base class constructor should be called before
# creating any widgets particular to the panel type.
#
# The main methods used here are the set_job and update methods:
# set_job modifies the job that the panel is displaying; update does
# the work of actually updating the panel display and is the main
# method overridden in the derived panel classes.


class FuzzyCombobox(ttk.Combobox):
    def __init__(self, master, **kw):
        super().__init__(master, **kw)
        self.bind("<KeyRelease>", self._on_keyrelease)
        self._original_values = kw.get("values", [])  # Store original dropdown values
        self._delay_ms = 1000  # Delay in milliseconds
        self._after_id = None  # Store the ID for the after method

    def _on_keyrelease(self, event):
        # Cancel existing delay
        if self._after_id:
            self.after_cancel(self._after_id)

        # Start a new delay
        self._after_id = self.after(self._delay_ms, self._filter_values)

    def _filter_values(self):
        # Filter logic here: update 'values' based on input
        filter_text = self.get()
        new_values = [
            value
            for value in self._original_values
            if filter_text.lower() in value.lower()
        ]
        self["values"] = new_values

        # Open the dropdown after filtering if there are matching values
        if new_values:
            self.event_generate("<Down>")

        self._after_id = None  # Reset the after ID


class Panel(ttk.Frame):
    """
    Base class for all panel types in the application GUI.

    A panel represents a page in the notebook part of the GUI, dedicated to displaying specific information.
    """

    def __init__(
        self, notebook: ttk.Notebook, app: Any, view_type: str, title: str
    ) -> None:
        """
        Initialize the Panel.

        :param notebook: The notebook widget this panel will be added to.
        :param app: The application object.
        :param view_type: The type of the panel.
        :param title: The title of the panel.
        """
        super().__init__(notebook)
        self.app = app
        self.view_type = view_type
        self.job = None  # Placeholder for the job object this panel will display information about.
        self.grid(column=0, row=0, padx=5, pady=5, sticky=tk.N + tk.S + tk.E + tk.W)
        notebook.add(self, text=title)

    def set_job(self, job: Any) -> None:
        """
        Sets the job object that this panel should display information about.

        :param job: The job object.
        """
        self.job = job
        self.update()

    def label(
        self, text: str, row: int, column: int = 0, font: Optional[str] = None
    ) -> ttk.Label:
        """
        Creates a label widget.

        :param text: The text to display in the label.
        :param row: The grid row where the label should be placed.
        :param column: The grid column where the label should be placed.
        :param font: The font to use for the label's text.
        :return: The created label widget.
        """
        label = ttk.Label(self, text=text, font=font)
        label.grid(column=column, row=row, pady=5, padx=5, sticky=tk.W)
        return label

    def clear(self) -> None:
        """
        Clears the panel's content. Overridden in some derived classes.
        """
        self.update()

    def update(self) -> None:
        """
        Updates the panel display with the current job's information.

        This method is intended to be overridden in derived panel classes to implement specific display logic.
        """
        pass  # To be implemented by subclasses


# ----------------------------------------------------------------------
#
#  STATUS PANEL
#

# The status panel is simple: it's read-only, so the update method
# just needs to read values from the current job and set the widgets
# to display them.


class StatusPanel(Panel):
    """
    StatusPanel displays the current status and details of a job within the GUI.

    It inherits from the base Panel class and adds specific widgets to display job details.
    """

    def __init__(self, notebook: ttk.Notebook, app: "Application") -> None:
        """
        Initialize the StatusPanel.

        :param notebook: The parent notebook widget.
        :param app: The application object, which provides context and access to shared resources.
        """
        super().__init__(notebook, app, "status", "Status")

        self.label("Job path:", 0, font=self.app.bold_font)
        self.job_path = ttk.Label(self, font=self.app.bold_font)
        self.job_path.grid(column=1, row=0, pady=5, sticky=tk.W)

        self.label("Job status:", 1)
        self.job_status = ttk.Label(self)
        self.job_status.grid(column=1, row=1, pady=5, sticky=tk.W)

        self.label("Run length:", 2)
        self.runlen = ttk.Label(self)
        self.runlen.grid(column=1, row=2, pady=5, sticky=tk.W)

        self.label("T100:", 3)
        self.t100 = ttk.Label(self)
        self.t100.grid(column=1, row=3, pady=5, sticky=tk.W)

        self.update()  # Fills in the display fields from the current job.

    def update(self) -> None:
        """
        Updates the panel display with the current job's information.
        Clears the display if no job is selected, or updates all fields
        with the job's current status and details.
        """
        if not self.job:
            # Clear all fields if no job is selected.
            self.job_path.configure(text="")
            self.job_status.configure(text="")
            self.runlen.configure(text="")
            self.t100.configure(text="")
        else:
            # Update fields with current job information.
            self.job_path.configure(text=self.job.jobdir_str())
            status_text = self.job.status_str()

            # Append percentage complete if the job is running.
            if status_text == "RUNNING":
                status_text += f" ({self.job.pct_done():.2f}%)"

            self.job_status.configure(text=status_text)
            self.runlen.configure(text=self.job.runlen_str())
            self.t100.configure(text=self.job.t100_str())


# ----------------------------------------------------------------------
#
#  NAMELIST PANEL
#

# The namelist panel is also relatively simple.  It has an option menu
# to select which namelist to display, plus a scrolled text area to
# display the contents of the namelist file.  The option menu
# selection and the scrolling of the namelist display are the only
# interactive elements here.  When the current job is updated, the
# update method reads the namelist files for the new current job to
# set up the widget states.


class NamelistPanel(Panel):
    def __init__(self, notebook, app):
        super().__init__(notebook, app, "namelists", "Namelists")

        self.sel_frame = ttk.Frame(self)
        lab = ttk.Label(self.sel_frame, text="Namelist:")
        lab.grid(
            column=0, row=0, padx=5, pady=5, sticky=tk.W
        )  # Move this line from configure_grid

        # Start with an empty namelist menu.
        nls = ()
        self.namelists = {}
        self.nl_var = tk.StringVar()
        self.nl_sel = ttk.OptionMenu(
            self.sel_frame, self.nl_var, None, *nls, command=self.set_namelist_text
        )

        # The scrolled text widget here is read-only.
        self.out = tk.Text(
            self, font=self.app.mono_font, state=tk.DISABLED, wrap=tk.NONE
        )
        self.out_scroll = ttk.Scrollbar(self, command=self.out.yview)
        self.out.config(yscrollcommand=self.out_scroll.set)

        # Configure grid layout for components.
        self.configure_grid()

    def configure_grid(self):
        """
        Configures the grid layout for the NamelistPanel widgets.
        """
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.sel_frame.grid(column=0, row=0, sticky=tk.W, pady=5)
        self.nl_sel.grid(column=1, row=0, sticky=tk.W)
        self.out.grid(column=0, row=1, sticky=tk.E + tk.W + tk.N + tk.S)
        self.out_scroll.grid(column=1, row=1, sticky=tk.N + tk.S)

    def set_namelist_text(self, event: tk.Event = None) -> None:
        """
        Updates the text widget to display the contents of the currently selected namelist.

        This method is the callback for the namelist option menu selection.

        :param event: The event that triggered this callback, if any.
        """
        self.out.config(state=tk.NORMAL)
        self.out.delete("1.0", tk.END)

        selected_namelist = self.nl_var.get()
        if selected_namelist:
            namelist_content = self.namelists.get(selected_namelist, "")
            self.out.insert(tk.END, namelist_content)

        self.out.config(state=tk.DISABLED)

    def update(self) -> None:
        """
        Updates the panel to display the namelists associated with the current job.
        """

    def update(self) -> None:
        """
        Updates the panel to display the namelists associated with the current job.
        """
        self.namelists = {}

        if self.job:
            # Use a list comprehension to gather all namelist filenames matching "data_*" in the job directory
            nls = [
                os.path.basename(nl)[5:]
                for nl in glob.iglob(os.path.join(self.job.jobdir, "data_*"))
            ]

            # Read the contents of each namelist file
            for nlname in nls:
                with open(os.path.join(self.job.jobdir, f"data_{nlname}"), "r") as fp:
                    self.namelists[nlname] = fp.read()

            nls.sort()
        else:
            nls = []

        # Update the namelist option menu
        menu = self.nl_sel["menu"]
        menu.delete(0, "end")

        for nl in nls:
            menu.add_command(
                label=nl, command=lambda value=nl: self.set_namelist(value)
            )

        # Enable or disable the namelist selection based on available namelists
        enable(self.nl_sel, bool(nls))

        # Set the initial value if namelists are available and the current value is not in the updated list
        if nls and self.nl_var.get() not in nls:
            self.nl_var.set(nls[0])
            self.set_namelist_text()

    def set_namelist(self, namelist: str) -> None:
        """
        Sets the currently selected namelist and updates the text widget.

        :param namelist: The name of the selected namelist.
        """
        self.nl_var.set(namelist)
        self.set_namelist_text()

    def configure_namelist_option_menu(self, nls: Tuple[str, ...]) -> None:
        """
        Configures the namelist option menu with available namelists.

        :param nls: A tuple of namelist names to populate the menu.
        """
        # Clear current menu options
        menu = self.nl_sel["menu"]
        menu.delete(0, "end")

        # Add new options
        for nl in nls:
            menu.add_command(label=nl, command=lambda value=nl: self.nl_var.set(value))

        # Set the initial value if namelists are available
        if nls:
            self.nl_var.set(nls[0])
            self.set_namelist_text()


# ----------------------------------------------------------------------
#
#  OUTPUT PANEL
#

# The output panel consists of a single scrolled text widget to
# display cTOASTER model standard output from the currently selected job.
# Real-time updates of the text widget are managed by a Tailer object,
# which is basically just a thing that looks at a file on a regular
# basis (using a Tkinter "after" timer) to see if there's any new
# content in the file, and if there is, passes that content to a
# user-specified callback.  The only complexity in the output panel
# class is involved in managing the tailer.


class OutputPanel(Panel):
    def __init__(self, notebook, app):
        super().__init__(notebook, app, "output", "Output")

        self.tailer = None  # The cTOASTER log file tailer.
        self.tailer_job = None  # The job that we're currently tailing.
        self.output_text = ""  # Full text in the log text widget.

        # Read-only scrolled text widget.
        self.out = tk.Text(self, font=self.app.mono_font, state=tk.DISABLED)
        self.out_scroll = ttk.Scrollbar(self, command=self.out.yview)
        self.out.config(yscrollcommand=self.out_scroll.set)

        self.configure_grid()

    def configure_grid(self):
        """
        Configures the grid layout for the OutputPanel widgets.
        """
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.out.grid(column=0, row=0, sticky=tk.E + tk.W + tk.N + tk.S)
        self.out_scroll.grid(column=1, row=0, sticky=tk.N + tk.S)

    def add_output_text(self, text: str, clear: bool = False) -> None:
        """
        Adds text to the scrolling output widget, optionally clearing the widget beforehand.

        If the end of the text is currently visible or if the text is being cleared, it ensures that
        the text scrolls to keep the end visible after adding the new text.

        :param text: The text to be added to the output widget.
        :param clear: A boolean indicating whether the output widget should be cleared before adding new text.
        """
        self.out.config(state=tk.NORMAL)
        if clear:
            self.output_text = text
            self.out.delete("1.0", tk.END)
        else:
            self.output_text += text

        at_end = self.out_scroll.get()[1] == 1.0
        self.out.insert(tk.END, text)
        self.out.config(state=tk.DISABLED)
        if at_end or clear:
            self.out.see(tk.END)

    def clear(self) -> None:
        """
        Clears the output text widget and stops the tailer that monitors the job output log.
        """
        # Stop the tailer if it's currently active.
        if self.tailer:
            self.tailer.stop()

        # Reset the tailer and job-related attributes.
        self.tailer = None
        self.tailer_job = None

        # Clear the text in the output widget.
        self.add_output_text("", clear=True)

    def update(self) -> None:
        """
        Updates the output panel display based on the current job selection.
        Clears the display if no job is selected or sets up a tailer to follow
        the job's run log.
        """
        if not self.job:
            # Clear the display if no job is currently selected.
            self.clear()
        else:
            # Determine the path to the job's run log.
            log = os.path.join(self.job.jobdir, "run.log")

            # Clear the display if the log file doesn't exist.
            if not os.path.exists(log):
                self.add_output_text("", clear=True)
                return

            # If a different job is being tailed, stop the current tailer.
            if self.tailer and self.tailer_job != self.job:
                self.clear()

            # Start a new tailer for the current job's run log, if not already tailing.
            if not self.tailer:
                self.tailer_job = self.job
                self.tailer = Tailer(self.app, log)
                self.tailer.start(self.add_output_text)


# ----------------------------------------------------------------------
#
#  PLOT PANEL
#

# The plot panel has option menu widgets for selecting a data file and
# a variable to plot and a large canvas area used to contain a
# matplotlib plot.
#
# The only real complexity in the code here is the slightly convoluted
# flow of control needed to manage populating the option menus based
# on the output files available for the selected job.  First, the job
# may not have written any output files yet, so we need to call the
# check_output_files on the job repeatedly until we find some files.
# When we do find some files, we can fill in the file selector option
# menu and select a file (by default, the first one).
#
# Once a data file has been selected, we need to determine what
# variables are available in the file by parsing the file's header
# (and to select the first variable to plot, by default).  However, we
# also need to set things up so that we can get real-time notification
# of changes in the contents of the file to be able to update the plot
# as new data is written by the model.  This is done using a helper
# class called TimeSeriesFile which abstracts the reading and parsing
# of the data file, but does mean there's a bit of bouncing back and
# forth between the PlotPanel code and the TimeSeriesFile code to get
# the list of variables to populate the variable option menu and the
# initial data to make a plot.
#
# Once a variable is selected, we can create an initial plot from the
# data currently help by the TimeSeriesFile object.  Then, as new data
# is written to the data file by the model, the TimeSeriesFile object
# notifies the PlotPanel by calling the data_update method, which
# brings in the new data to plot and rescales and redraws the plot.
#
# All of this sounds a bit complicated, but it uses exactly the same
# logic for the initial setup as for user interaction with the data
# file and data variable option menus.


class PlotPanel(Panel):
    def __init__(self, notebook, app):
        Panel.__init__(self, notebook, app, "plots", "Plots")

        # The job that we're plotting data from (used for managing
        # some logic in the update method).
        self.plot_job = None

        # The time series follower.
        self.ts_file = None

        # Create the matplotlib figure and plot objects that we're
        # going to use.
        self.fig = plt.figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.plot = None

        # Set up option menus for selecting the data file to plot from
        # and the variable within the file to plot.  These are both
        # empty and disabled to start with and are filled in by the
        # check_job_files, file_changed and data_update methods.
        self.choice_frame = ttk.Frame(self)
        lab = ttk.Label(self.choice_frame, text="Data file:")
        lab.pack(side=tk.LEFT, padx=5)
        self.files = ()
        self.file_var = tk.StringVar()
        self.file_sel = ttk.OptionMenu(
            self.choice_frame,
            self.file_var,
            None,
            *self.files,
            command=self.file_changed,
        )
        enable(self.file_sel, False)
        self.file_sel.pack(side=tk.LEFT, padx=5)
        lab = ttk.Label(self.choice_frame, text="")
        lab.pack(side=tk.LEFT, padx=5)
        lab = ttk.Label(self.choice_frame, text="Variable:")
        lab.pack(side=tk.LEFT, padx=5)
        self.vars = ()
        self.var_var = tk.StringVar()
        self.var_sel = ttk.OptionMenu(
            self.choice_frame, self.var_var, None, *self.vars, command=self.var_changed
        )
        enable(self.var_sel, False)
        self.var_sel.pack(side=tk.LEFT, padx=5)

        # Create a Tkinter canvas to hold the plot and instantiate
        # everything.
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.choice_frame.pack(side=tk.TOP, pady=10, anchor=tk.NW)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def clear(self):
        # Clear everything -- set option menus to empty and disabled,
        # clear plot and restart job file checking.
        if self.ts_file:
            self.ts_file.stop()
        self.ts_file = None
        self.plot_job = None
        self.files = ()
        self.vars = ()
        self.file_sel.set_menu(None, *self.files)
        self.file_var.set("")
        enable(self.file_sel, False)
        self.var_sel.set_menu(None, *self.vars)
        self.var_var.set("")
        enable(self.var_sel, False)
        self.output_files = {}
        self.ax.clear()
        self.canvas.draw()
        self.after(0, self.check_job_files)

    def update(self):
        # If the job we're supposed to be plotting changes from the
        # job we currently are plotting, we just clear the plot and
        # start the check_job_files timer, which will pick up any job
        # data files and repopulate the GUI.
        if self.job != self.plot_job:
            self.clear()
            self.plot_job = self.job
            if self.job:
                self.after(0, self.check_job_files)

    def check_job_files(self):
        # This method is called on a timer as long as we don't have
        # any data files. Once it finds files, it uses them to
        # populate the file option menu, selects the first one, and
        # signals that the selected file has been updated by calling
        # the file_changed method.
        if self.job and not self.files:
            self.output_files = self.job.check_output_files()
            self.files = list(self.output_files.keys())  # Convert dict_keys to a list
            if self.files:
                self.files.sort()  # Now you can sort the list

                # Assuming set_menu is a custom method that correctly updates the option menu
                # If ttk.OptionMenu is being used and there's no set_menu, this needs adjustment
                self.file_sel.set_menu(self.files[0], *self.files)
                self.file_var.set(self.files[0])
                enable(self.file_sel, True)
                self.file_changed()
            self.after(500, self.check_job_files)

    def file_changed(self, event=None):
        # A new data file has been selected in the file option menu,
        # so clear the data variable option menu, work out the path to
        # the data file and create a TimeSeriesFile object to manage
        # reading data from the file.  The TimeSeriesFile class is a
        # specialisation of the Tailer class for dealing with BIOGEM
        # ASCII output data files.  It tails the data file and parses
        # the data lines to pick out time and variable values; a
        # user-provided callback (here, the data_update method) is
        # called whenever there's new data.
        if self.file_var.get():
            tsp = self.output_files[self.file_var.get()]
            self.vars = ()
            self.var_sel.set_menu(None, *self.vars)
            self.var_var.set("")
            enable(self.var_sel, False)
            self.ts_file = TimeSeriesFile(self.app, tsp, self.data_update)
        else:
            self.ts_file = None

    def data_update(self, tnew, dnew):
        if self.vars == ():
            # The first time this gets called, we need to set up the
            # data variable option menu in the GUI, based on the data
            # file header parsed by the TimeSeriesFile object. We
            # select the first available variable and signal that the
            # selected variable has changed by calling the var_changed
            # method.
            self.vars = self.ts_file.vars
            self.var_sel.set_menu(None, *self.vars)
            enable(self.var_sel, True)
            self.ax.clear()
            if len(self.vars) >= 1:
                self.var_var.set(self.vars[0])
                self.var_changed()
            else:
                self.canvas.draw()
        else:
            # Update the plot data using the new time values (tnew) and data values (dnew)
            var_name = self.var_var.get()
            if var_name in self.ts_file.data:
                # Convert the data to float for plotting
                ts_file_time_float = [float(val) for val in self.ts_file.time]
                ts_file_data_float = [float(val) for val in self.ts_file.data[var_name]]

                # Clear the previous plot
                self.ax.clear()

                # Plot the data
                self.ax.plot(
                    ts_file_time_float, ts_file_data_float, label="ts_file_data"
                )
                self.ax.set_xlabel("Time")
                self.ax.set_ylabel(var_name)
                self.ax.set_title("Plot of " + var_name)
                self.ax.legend()
                self.ax.relim()
                self.ax.autoscale_view()
                self.ax.xaxis.set_major_locator(ticker.LinearLocator(numticks=10))
                self.ax.yaxis.set_major_locator(ticker.LinearLocator(numticks=10))

                self.canvas.draw()

    def var_changed(self, event=None):
        # The selected variable has changed, so clear the plot, get
        # the current time and data values from the TimeSeriesFile
        # object and draw an initial plot. This is then updated in
        # real-time by the data_update method as more data is read
        # from the time series file.
        self.ax.clear()

        var_name = self.var_var.get()
        if var_name in self.ts_file.data:
            # Convert the data to float for plotting
            ts_file_time_float = [float(val) for val in self.ts_file.time]
            ts_file_data_float = [float(val) for val in self.ts_file.data[var_name]]

            # Plot the data
            (self.plot,) = self.ax.plot(ts_file_time_float, ts_file_data_float)
            self.ax.set_xlabel("Time (yr)")
            self.ax.set_ylabel(var_name)
            self.ax.set_title("Plot of " + var_name)
            self.ax.relim()
            self.ax.autoscale_view()
            self.ax.xaxis.set_major_locator(ticker.LinearLocator(numticks=10))
            self.ax.yaxis.set_major_locator(ticker.LinearLocator(numticks=10))

            self.canvas.draw()


# ----------------------------------------------------------------------
#
#  SETUP PANEL
#

# This is the most complicated of the panels.  It has a lot of
# interactive widgets, displays a lot of information and has some
# complicated interaction patterns.  Basically though, its purpose is
# simple: to generate cTOASTER namelists based on user-selected
# configuration files, configuration "modifications" and other
# information.  Much of the complexity stems from the need to support
# configuration changes when a model run is paused and restarted: the
# configuration before the pause needs to be saved away somewhere and
# made available for viewing by the user while the configuration at
# the point where the model is paused should be editable and saveable.


class SetupPanel(Panel):
    def __init__(self, notebook, app):
        Panel.__init__(self, notebook, app, "setup", "Setup")

        # Read-only display of path to job directory.
        self.label("Job path:", 0, font=self.app.bold_font)
        self.job_path = ttk.Label(self, font=self.app.bold_font)
        self.job_path.grid(column=1, row=0, pady=5, sticky=tk.W)

        # Run segment option menu used for displaying earlier
        # configurations from before "pause and edit" actions.
        self.label("Run segment:", 1)
        if self.job:
            self.segments = self.job.segment_strs()
        else:
            self.segments = ("1: 1-END",)
        self.segment_var = tk.StringVar()
        self.segment_sel = ttk.OptionMenu(
            self, self.segment_var, None, *self.segments, command=self.segment_changed
        )
        self.segment_sel.grid(column=1, row=1, pady=5, sticky=tk.W)
        self.segment_var.set(self.segments[0])
        self.current_seg = self.segments[0]
        enable(self.segment_sel, len(self.segments) > 1)

        # Base configuration: the available base configuration files
        # are determined at startup by the main application object.
        self.label("Base config:", 2)
        # Base Config Combobox without "readonly" state
        self.base_config = FuzzyCombobox(self, values=self.app.base_configs, width=80)
        self.base_config.bind("<<ComboboxSelected>>", self.state_change)
        self.base_config.grid(column=1, row=2, pady=5, sticky=tk.W)
        # User configuration: the available base configuration files
        # are determined at startup by the main application object.
        self.label("User config:", 3)
        # User Config Combobox without "readonly" state
        self.user_config = FuzzyCombobox(self, values=self.app.user_configs, width=80)
        self.user_config.bind("<<ComboboxSelected>>", self.state_change)
        self.user_config.grid(column=1, row=3, pady=5, sticky=tk.W)
        # Configuration modifications: this is a free-form text field
        # that can be used for quick "overlay" modifications to the
        # job configuration.  The namelist files are generated by
        # overlaying the user configuration on the base configuration,
        # then overlaying the configuration modifications on top of
        # that.
        self.label("Modifications:", 4)
        self.mods_frame = ttk.Frame(self)
        self.mods_frame.grid(column=1, row=4, pady=5, sticky=tk.W)
        self.mods = tk.Text(
            self.mods_frame, width=80, height=20, font=self.app.normal_font
        )
        self.mods.bind("<<Modified>>", self.state_change)
        self.mods_scroll = ttk.Scrollbar(self.mods_frame, command=self.mods.yview)
        self.mods["yscrollcommand"] = self.mods_scroll.set
        self.mods.grid(column=0, row=0, sticky=tk.W)
        self.mods_scroll.grid(column=1, row=0, sticky=tk.N + tk.S)

        # Simulation run length in years.  This has a validator to
        # make sure that only valid numerical values are input.  [Note
        # that the ttk.Entry widget doesn't seem to have anything like
        # a <<Modified>> virtual event, so instead the trace method of
        # the Tkinter StringVar class is used to detect when the value
        # has changed.]
        self.label("Run length:", 5)
        self.check = self.register(self.check_runlen)
        self.runlen_var = tk.StringVar()
        self.runlen = ttk.Entry(
            self,
            width=20,
            validate="all",
            textvariable=self.runlen_var,
            validatecommand=(self.check, "%P"),
        )
        self.runlen.grid(column=1, row=5, pady=5, sticky=tk.W)
        self.runlen_var.trace("w", self.state_change)

        # The T100 flag: just a checkbox.
        self.label("T100:", 6)
        self.t100_var = tk.IntVar()
        self.t100 = ttk.Checkbutton(
            self, variable=self.t100_var, command=self.state_change
        )
        self.t100.grid(column=1, row=6, pady=5, sticky=tk.W)

        # Restart job selection: the only jobs that are allowed as
        # restart jobs are those that have successfully completed; a
        # list of such jobs is maintained by the main application
        # object for use here.
        self.label("Restart from:", 7)
        # Restart Config Combobox without "readonly" state
        self.restart = FuzzyCombobox(self, values=self.app.restart_jobs, width=80)
        self.restart.bind("<<ComboboxSelected>>", self.state_change)
        self.restart.grid(column=1, row=7, pady=5, sticky=tk.W)
        # Save and revert buttons.
        self.but_frame = ttk.Frame(self)
        self.but_frame.grid(column=1, row=8, pady=5, sticky=tk.W)
        self.save_button = ttk.Button(
            self.but_frame, text="Save changes", command=self.save_changes
        )
        self.revert_button = ttk.Button(
            self.but_frame, text="Revert changes", command=self.revert_changes
        )
        self.save_button.grid(column=0, row=0)
        self.revert_button.grid(column=1, row=0, padx=5)

        # Has anything been changed since the last save?
        self.edited = False

        # Is there enough information to generate namelists and switch
        # the job state from UNCONFIGURED to RUNNABLE?
        self.complete = False

        # Hand off setting up widget values to update method.
        self.update()

    def update(self):
        # Set up default values for everything.
        self.restart.configure(values=self.app.restart_jobs)
        self.restart.set("<None>")
        self.base_config.set("")
        self.user_config.set("")
        self.mods.delete("1.0", "end")
        self.runlen.delete(0, "end")
        self.t100_var.set(False)

        # Set up run segment selector list: populated from the job
        # data if possible; disabled if there is only one segment.
        if self.job:
            self.segments = self.job.segment_strs()
        else:
            self.segments = ("1: 1-END",)
        self.segment_sel.set_menu(self.segments[0], *self.segments)
        self.current_seg = self.segments[0]
        enable(self.segment_sel, len(self.segments) > 1)

        # Enable or disable save/revert buttons depending on state.
        self.set_button_state()

        if not self.job:
            return

        # We have a real job, so set widget values from the job.
        # [Note that '?' is used as a placeholder in the initial
        # config file written when a new job is created, and these are
        # picked out as a special case for some fields below.]
        self.job_path.configure(text=self.job.jobdir_str())
        if self.job.base_config:
            self.base_config.set(
                self.job.base_config if self.job.base_config != "?" else ""
            )
        else:
            self.base_config.set("")
        if self.job.user_config:
            self.user_config.set(
                self.job.user_config if self.job.user_config != "?" else ""
            )
        else:
            self.user_config.set("")
        self.restart.set(self.job.restart if self.job.restart else "<None>")
        self.mods.delete("1.0", "end")
        if self.job.mods:
            self.mods.insert("end", self.job.mods)
        self.runlen.delete(0, "end")
        if self.job.runlen != None:
            self.runlen.insert("end", str(self.job.runlen))
        self.t100_var.set(bool(self.job.t100))
        if self.job:
            self.segments = self.job.segment_strs()
        else:
            self.segments = ("1: 1-END",)
        self.segment_sel.set_menu(self.segments[0], *self.segments)

        # Now determine the current edited/complete state and set the
        # button states appropriately.
        self.set_state()
        self.set_button_state()

    def check_runlen(self, s):
        # Validator for run length field values: must be a positive
        # integer.
        try:
            v = s.strip()
            if not v:
                return True
            return int(v) > 0
        except:
            return False

    def set_button_state(self):
        # You can only "save" (which generates namelists) if the setup
        # has been edited and is complete; and you can only "revert"
        # if the setup has been edited.
        enable(self.save_button, self.edited and self.complete)
        enable(self.revert_button, self.edited)

    def set_state(self):
        # If there's no job selected, these don't make sense anyway.
        self.complete = False
        self.edited = False
        if self.job:
            # The minimal information needed to set up a job is a base
            # config, a user config and a run length.
            self.complete = (
                self.base_config.get() and self.user_config.get() and self.runlen.get()
            )

            # Check for changes by comparing widget values with the
            # values in the current job.
            if (
                self.base_config.get()
                and self.base_config.get() != self.job.base_config
            ):
                self.edited = True
            if (
                self.user_config.get()
                and self.user_config.get() != self.job.user_config
            ):
                self.edited = True
            if self.mods.get("1.0", "end").rstrip() != self.job.mods.rstrip():
                self.edited = True
            if self.runlen.get() and int(self.runlen.get()) != self.job.runlen:
                self.edited = True
            if self.t100_var.get() != self.job.t100:
                self.edited = True
            r = self.restart.get()
            if r == "<None>":
                r = None
            if r != self.job.restart:
                self.edited = True

    def state_change(self, event=None, dummy1=None, dummy2=None):
        # This is used as a general callback for all changes to the
        # setup widgets: set_state and set_button_state do most of the
        # work.
        self.set_state()
        self.set_button_state()

        # The <<Modified>> virtual event provided by the tk.Text
        # widget is a "sticky" notification, so it needs to be reset
        # here so that we get notified of *all* changes to the
        # configuration modifications text.
        self.mods.edit_modified(False)

    def save_changes(self):
        # Save configuration changes into the currently selected job and

        # Save changes to current job.
        self.job.base_config = self.base_config.get()
        self.job.user_config = self.user_config.get()
        self.job.mods = self.mods.get("1.0", "end").rstrip()
        new_runlen = int(self.runlen_var.get())
        runlen_increased = self.job.runlen != None and new_runlen > self.job.runlen
        self.job.runlen = new_runlen
        self.job.t100 = True if self.t100_var.get() else False
        r = self.restart.get()
        if r == "<None>":
            r = None
        self.job.restart = r

        # Write new configuration files (also manages run segments if
        # required) and generate new namelists.
        self.job.write_config()
        self.job.gen_namelists()

        # Manage updates in other parts of the GUI, in particular the
        # status icon for the current job in the job tree and the
        # other panels.
        self.job.set_status(runlen_increased)
        self.app.tree.item(self.job.jobdir, image=self.job.status_img())

        for _, p in self.app.panels.items():
            p.update()

        # Update the setup panel state.
        self.set_state()
        self.set_button_state()

    def revert_changes(self):
        # Reset widget values from currently selected job.
        self.base_config.set(self.job.base_config if self.job.base_config else "")
        self.user_config.set(self.job.user_config if self.job.user_config else "")
        self.mods.delete("1.0", "end")
        if self.job.mods:
            self.mods.insert("end", self.job.mods)
        self.runlen.delete(0, "end")
        if self.job.runlen != None:
            self.runlen.insert("end", str(self.job.runlen))
        self.t100_var.set(bool(self.job.t100))
        self.restart.set(self.job.restart if self.job.restart else "<None>")
        self.state_change(None)

    def segment_changed(self, event):
        # Callback for run segment option menu: the basic idea here is
        # that the "current" segment is editable, all earlier segments
        # are read-only.  The code here mostly just deals with getting
        # configuration information either from the segment
        # information for the current job, or from widget values saved
        # when we switch away from the current segment.
        seg = int(self.segment_var.get().split(":")[0])
        was_current = self.current_seg.endswith("END")
        now_current = self.segment_var.get().endswith("END")
        self.current_seg = self.segment_var.get()
        self.mods.configure(state=tk.NORMAL)
        if was_current:
            self.base_config_save = self.base_config.get()
            self.user_config_save = self.user_config.get()
            self.mods_save = self.mods.get("1.0", "end")
            self.runlen_save = self.runlen.get()
            self.t100_save = self.t100_var.get()
            self.restart_save = self.restart.get()
        if now_current:
            self.base_config.set(self.base_config_save)
            self.user_config.set(self.user_config_save)
            self.mods.delete("1.0", "end")
            self.mods.insert("end", self.mods_save)
            self.runlen_var.set(self.runlen_save)
            self.t100_var.set(self.t100_save)
            self.restart.set(self.restart_save)
        else:
            vals = self.job.read_segment(seg)
            self.base_config.set(vals["base_config"] if "base_config" in vals else "")
            self.user_config.set(vals["user_config"] if "user_config" in vals else "")
            self.mods.delete("1.0", "end")
            if "mods" in vals:
                self.mods.insert("end", vals["mods"])
            self.runlen_var.set(vals["runlen"])
            self.t100_var.set(vals["t100"])
            self.restart.set(vals["restart"] if "restart" in vals else "")
        enable(self.base_config, now_current)
        enable(self.user_config, now_current)
        self.mods.configure(state=tk.NORMAL if now_current else tk.DISABLED)
        enable(self.runlen, now_current)
        enable(self.t100, now_current)
        enable(self.restart, now_current)
        if now_current:
            self.state_change()
        else:
            enable(self.save_button, False)
            enable(self.revert_button, False)
