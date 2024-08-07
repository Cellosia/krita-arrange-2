from krita import Krita, Extension, Qt, QWidget, QDockWidget, QFrame, QHBoxLayout, QGridLayout, QRadioButton, QToolButton, QIcon, QLabel, QSpacerItem, QSizePolicy, QGraphicsOpacityEffect
from . import operators as op
import pathlib

class extensionArrange2(Extension):
	""" Register Arrange 2 Extension """

	def __init__(self, parent):
		super().__init__(parent)

		app = Krita.instance()

		appNotifier = app.notifier()
		appNotifier.setActive(True)
		appNotifier.windowIsBeingCreated.connect(self.create_panel)
		appNotifier.windowCreated.connect(self.window_ready)
		self.notifier = appNotifier

		# Load plugin settings
		# Default anchor value is None == all selected layers
		self.anchor = Krita.instance().readSetting("", "pluginArrange2.Anchor", None)
	# ----------------------------------------------------------------------------------------------

	def setup(self):
		pass

	def createActions(self, window):
		pass

	def window_ready(self):
		""" Connect notfiers for window that was just finished being created """
		app = Krita.instance()
		window = app.activeWindow()

		# Update custom icons colors when theme changes
		window.themeChanged.connect(self.update_icons_theme)

	def get_anchor(self):
		""" Retrieve the current alignment anchor """
		return self.anchor

	def update_anchor(self, value=None):
		""" Enable or disable and update appearance of tool buttons, and update setting """

		# Disable button if chosen mode doesn't apply to it
		if value == "canvas" or value == "active":
			# Canvas only works for alignment operations
			# Active layer only works for alignment operations
			for btn in self.btns_anchor_all_only:
				# Signal button is disabled by fading it
				btn.graphicsEffect().setEnabled(True)
				btn.setEnabled(False)
				pass
		else:
			# Selected layers apply to all kinds of operations
			for btn in self.btns_anchor_all_only:
				opacity_effect = btn.graphicsEffect().setEnabled(False)
				btn.setEnabled(True)
				pass

		self.anchor = value

		# Save Setting
		Krita.instance().writeSetting("", "pluginArrange2.Anchor", self.anchor)

	def update_icons_theme(self):
		""" Update the color of custom icons to match the theme """
		# Filtering themes names because I couldn't find a setting making direct references to icon color :|
		theme = Krita.instance().readSetting("theme", "Theme", "dark").lower()
		theme = "light" if ("dark" in theme or "blender" in theme or "contrast" in theme) else "dark"

		icons_path = f"{pathlib.Path(__file__).parent.absolute()}/icons/{theme}_arrange_edge-to-edge"

		self.btn_dist_edge_left.setIcon(QIcon(f"{icons_path}_left.svg"))
		self.btn_dist_edge_right.setIcon(QIcon(f"{icons_path}_right.svg"))
		self.btn_dist_edge_top.setIcon(QIcon(f"{icons_path}_top.svg"))
		self.btn_dist_edge_bottom.setIcon(QIcon(f"{icons_path}_bottom.svg"))

	def create_align_button(self, id, icon, tooltip, action, placement, **kwargs):
		btn = QToolButton()
		if icon is not None:
			btn.setIcon(icon)
		btn.setToolTip(tooltip)
		btn.setObjectName(id)
		btn.clicked.connect(lambda: action(placement, **kwargs))

		return btn

	def create_panel(self, window):
		""" Generate GUI alignment panel for the new window being created """
		qwin = window.qwindow()
		qdock = qwin.findChild(QDockWidget, "ArrangeDocker", options=Qt.FindDirectChildrenOnly).findChild(QWidget, 'ArrangeDockerWidget', options=Qt.FindDirectChildrenOnly)

		# Create a new layout to hold updated alignment buttons
		layout = QGridLayout()
		layout.setObjectName("raster_layout")

		app = Krita.instance()

		# --- Create buttons
		btn_align_left = self.create_align_button("btn_align_left", app.icon('object-align-horizontal-left-calligra'), "Align left edges", op.align_nodes, "left", anchor=self.get_anchor)
		btn_align_center_h = self.create_align_button("btn_align_center_h", app.icon('object-align-horizontal-center-calligra'), "Align horizontally", op.align_nodes, "h_center", anchor=self.get_anchor)
		btn_align_right = self.create_align_button("btn_align_right", app.icon('object-align-horizontal-right-calligra'), "Align right edges", op.align_nodes, "right", anchor=self.get_anchor)

		btn_align_top = self.create_align_button("btn_align_top", app.icon('object-align-vertical-top-calligra'), "Align top edges", op.align_nodes, "top", anchor=self.get_anchor)
		btn_align_center_v = self.create_align_button("btn_align_center_v", app.icon('object-align-vertical-center-calligra'), "Align vertically", op.align_nodes, "v_center", anchor=self.get_anchor)
		btn_align_bottom = self.create_align_button("btn_align_bottom", app.icon('object-align-vertical-bottom-calligra'), "Align bottom edges", op.align_nodes, "bottom", anchor=self.get_anchor)

		btn_dist_left = self.create_align_button("btn_dist_left", app.icon('distribute-horizontal-left'), "Distribute left edges evenly", op.distribute_nodes, "left")
		btn_dist_center_h = self.create_align_button("btn_dist_center_h", app.icon('distribute-horizontal-center'), "Distribute centers horizontally", op.distribute_nodes, "h_center")
		btn_dist_right = self.create_align_button("btn_dist_right", Krita.instance().icon('distribute-horizontal-right'), "Distribute right edges evenly", op.distribute_nodes, "right")

		btn_dist_top = self.create_align_button("btn_dist_top", app.icon('distribute-vertical-top'), "Distribute top edges evenly", op.distribute_nodes, "top")
		btn_dist_center_v = self.create_align_button("btn_dist_center_v", app.icon('distribute-vertical-center'), "Distribute centers vertically", op.distribute_nodes, "v_center")
		btn_dist_bottom = self.create_align_button("btn_dist_bottom", app.icon('distribute-vertical-bottom'), "Distribute bottom edges evenly", op.distribute_nodes, "bottom")

		btn_dist_h = self.create_align_button("btn_dist_h", app.icon('distribute-horizontal'), "Make horizontal spacing equal", op.distribute_nodes, "horizontal")
		btn_dist_v = self.create_align_button("btn_dist_v", app.icon('distribute-vertical'), "Make vertical spacing equal", op.distribute_nodes, "vertical")

		# New type of distribute, edge to edge without gaps
		btn_dist_edge_left = self.create_align_button("btn_dist_edge_left", None, "Place edge-to-edge from the left", op.distribute_nodes, "horizontal", spacing=0)
		btn_dist_edge_right = self.create_align_button("btn_dist_edge_right", None, "Place edge-to-edge from the right", op.distribute_nodes, "horizontal", spacing=0, reverse=True)
		btn_dist_edge_top = self.create_align_button("btn_dist_edge_top", None, "Place edge-to-edge from the top", op.distribute_nodes, "vertical", spacing=0)
		btn_dist_edge_bottom = self.create_align_button("btn_dist_edge_bottom", None, "Place edge-to-edge from the bottom", op.distribute_nodes, "vertical", spacing=0, reverse=True)

		# Store these to enable/disable on anchor type selection
		self.btns_anchor_all_only = [
			btn_dist_left,
			btn_dist_center_h,
			btn_dist_right,
			btn_dist_top,
			btn_dist_center_v,
			btn_dist_bottom,
			btn_dist_v,
			btn_dist_h,
			btn_dist_edge_left,
			btn_dist_edge_right,
			btn_dist_edge_top,
			btn_dist_edge_bottom,
		]

		# Setup opacity effect for when buttons are disabled
		for btn in self.btns_anchor_all_only:
			opacity_effect = QGraphicsOpacityEffect()
			opacity_effect.setOpacity(0.55)
			opacity_effect.setEnabled(False) # Don't enable effect yet
			btn.setGraphicsEffect(opacity_effect)

		self.btn_dist_edge_left = btn_dist_edge_left
		self.btn_dist_edge_right = btn_dist_edge_right
		self.btn_dist_edge_top = btn_dist_edge_top
		self.btn_dist_edge_bottom = btn_dist_edge_bottom

		# Ensure custom button icons have correct colors
		self.update_icons_theme()

		# --- Radio buttons
		rbtn_canvas = QRadioButton("Canvas")
		rbtn_canvas.toggled.connect(lambda: self.update_anchor("canvas"))
		rbtn_canvas.setToolTip("Align selection relative to canvas (edges only)")
		rbtn_canvas.setObjectName("rbtn_canvas")

		rbtn_active_layer = QRadioButton("Active")
		rbtn_active_layer.toggled.connect(lambda: self.update_anchor("active"))
		rbtn_active_layer.setToolTip("Align selection relative to active layer (edges only)")
		rbtn_active_layer.setObjectName("rbtn_active_layer")

		rbtn_selected_layers = QRadioButton("Selected")
		rbtn_selected_layers.toggled.connect(lambda: self.update_anchor(None))
		rbtn_selected_layers.setToolTip("Align selection relative to selected layers")
		rbtn_selected_layers.setObjectName("rbtn_selected_layers")


		# Set according to stored setting
		if self.anchor == "canvas":
			rbtn_canvas.setChecked(True)
		elif self.anchor == "active":
			rbtn_active_layer.setChecked(True)
		else:
			rbtn_selected_layers.setChecked(True)

		# --- Place elements in layout
		rc = 0  # Row count
		subheading = QLabel("Align Layers Relative to")
		layout.addWidget(subheading, rc, 0, 1, 7)

		rc += 1
		sublayout_wrapper = QWidget()
		sublayout = QHBoxLayout()
		sublayout.setContentsMargins(0, 0, 0, 3)

		sublayout.addWidget(rbtn_active_layer)
		sublayout.addWidget(rbtn_selected_layers)
		sublayout.addWidget(rbtn_canvas)
		sublayout_wrapper.setLayout(sublayout)

		layout.addWidget(sublayout_wrapper, rc, 0, 1, 7)

		rc += 1
		layout.addWidget(btn_align_left, rc, 0)
		layout.addWidget(btn_align_center_h, rc, 1)
		layout.addWidget(btn_align_right, rc, 2)
		#
		layout.addWidget(btn_align_top, rc, 4)
		layout.addWidget(btn_align_center_v, rc, 5)
		layout.addWidget(btn_align_bottom, rc, 6)

		rc += 1
		subheading = QLabel("Distribute Layers")
		subheading.setProperty("class", "subheading")
		layout.addWidget(subheading, rc, 0, 1, 7)
		rc += 1
		layout.addWidget(btn_dist_left, rc, 0)
		layout.addWidget(btn_dist_center_h, rc, 1)
		layout.addWidget(btn_dist_right, rc, 2)
		#
		layout.addWidget(btn_dist_top, rc, 4)
		layout.addWidget(btn_dist_center_v, rc, 5)
		layout.addWidget(btn_dist_bottom, rc, 6)

		rc += 1
		subheading = QLabel("Set Layers Spacing")
		subheading.setProperty("class", "subheading")
		layout.addWidget(subheading, rc, 0, 1, 7)
		rc += 1
		layout.addWidget(btn_dist_h, rc, 0)
		layout.addWidget(btn_dist_v, rc, 1)
		#
		layout.addWidget(btn_dist_edge_left, rc, 3)
		layout.addWidget(btn_dist_edge_right, rc, 4)
		layout.addWidget(btn_dist_edge_top, rc, 5)
		layout.addWidget(btn_dist_edge_bottom, rc, 6)

		# Grow last column to push layout to the left
		layout.setColumnStretch(7, 1)

		# Add a spacer to push layout up
		rc += 1
		vertical_spacer = QSpacerItem(40, 16, QSizePolicy.Minimum, QSizePolicy.Expanding)
		layout.addItem(vertical_spacer, rc, 0, 1, 7)
		# Give a minimum height to last row with spacer to create
		# 	a nice negative space at the bottom of the panel
		layout.setRowMinimumHeight(rc, 16)

		self.docker = qdock
		self.layout = layout
		self.frame = self.docker.findChild(QFrame, "disabledLabel")
		self.vector_frame = self.docker.findChild(QFrame, "buttons")

		# Style elements
		style = """
			#disabledLabel QToolButton { border: none; }

			#disabledLabel > QLabel.subheading { margin-top: 1.5ex; }
			#disabledLabel { min-width: 35ex; max-width: 55ex; }
		"""
		self.frame.setStyleSheet(style)

		# --- Reuse warning frame to hold new alignment buttons
		# Can't delete previous layout with Activate Shapes Tool message
		# 	at this point or Krita will crash. Eat it instead.
		self.placeholder = QWidget()
		layout.addWidget(self.placeholder)
		self.placeholder.setLayout(self.frame.layout())
		self.placeholder.hide()
		# self.frame.layout().deleteLater()
		# Set new layout
		self.frame.setLayout(layout)
		self.frame.adjustSize()

		# Fix an issue with the vector version of the docker in which it'll
		# 	grow in height when activated for no reason, squeezing other dockers.
		# 	It's happening because it's missing a minimum height value.
		qdock.setMinimumHeight(self.frame.height())
		qdock.adjustSize()


# And add the extension to Krita's list of extensions:
Krita.instance().addExtension(extensionArrange2(Krita.instance()))
