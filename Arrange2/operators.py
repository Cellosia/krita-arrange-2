from krita import Krita, QRect, QPoint

exclusion_list = {"filterlayer", "filllayer"}
exclusion_list_with_masks = {"filterlayer", "filllayer", "transparencymask", "filtermask", "colorizemask", "transformmask", "selectionmask"}
masks_list = {"transparencymask", "filtermask", "colorizemask", "transformmask", "selectionmask"}


######################## Operator Methods ##########################

def align_nodes(mode="left", **params):
	""" Align selected layers in a given direction relative to the anchor bounds.
		The anchor can be a layer, a selection of layers, or the canvas.
		@param mode: Edge to which layers will be aligned, default left.
		@param params: anchor function to retrieve selected anchor at runtime """

	anchor = params["anchor"]()

	app = Krita.instance()
	doc = app.activeDocument()
	view =  app.activeWindow().activeView()

	selected_nodes = view.selectedNodes()
	active_node = doc.activeNode()
	nodes_count = len(selected_nodes)

	# Align requires 1+ layer in canvas mode or 2+ in the other modes
	if not (anchor == "canvas" or nodes_count > 1):
		return False

	active_type = active_node.type()

	# Anchor can be the active node, the canvas, or None (average selected nodes positions)
	if (anchor == "canvas" or active_type in exclusion_list):
		''' Anchor is the canvas or a boundless layer '''
		# 	Happens with fill, filter layers. Use doc rect instead.
		anchor = doc
		rect = anchor.bounds() # Rect for anchoring
	elif anchor == "active":
		''' Anchor is the active layer, which should never move '''
		anchor = active_node
		anchor_type = anchor.type()
		rect = anchor.bounds()
		if anchor_type == "clonelayer":
			''' The active layer is a clone layer '''
			# BUG FIX: A hopefully temporary fix for clone layer buggy bounds
			rect = correct_clone_bounds(anchor, rect)
			# Don't remove it from selected nodes because it'll need a position fix
		elif anchor_type == "grouplayer":
			''' The active layer is a group layer that could contain clones, must fix rect '''
			stack = anchor.findChildNodes("", True)
			rect = calculate_group_bounds(stack)
			# Add any possible clones to list of clone layers to be processed
			# clone_nodes += anchor.findChildNodes("", True, False, "clonelayer")
			# Don't remove it from selected nodes due possible clone again.
			# 	If it's ever removed but clones remain relative you'll need to
			# 	do a clone_nodes += anchor.findChildNodes() here.
		else:
			# Remove active layer from selection being moved
			selected_nodes.remove(active_node)
	elif anchor is None:
		''' Anchor is a selection of layers '''
		# BUG FIX: Retrieve bounds while taking possible clone layers into account
		rect = calculate_group_bounds(selected_nodes)

	# --- Retrieve all possible clone layers in selection, sorted by ancestrors
	# 	and process them after regular layers because otherwise they
	# 	would move off-position if a source is moved after them.
	clone_nodes = [x for x in selected_nodes if x.type() == "clonelayer"]
	# Retrieve clones in groups as well
	for node in selected_nodes:
		clone_nodes += node.findChildNodes("", True, False, "clonelayer")
	# Build a list of all clones and sources to keep track of their movements
	partial_clones_list = {}
	for node in clone_nodes:
		partial_clones_list = get_clone_sources(node, selected_nodes, partial_clones_list, [], 0)
	clone_nodes = partial_clones_list

	is_moving_clones = bool(len(clone_nodes))

	# --- Loop through selected layers, aligning them
	for node in selected_nodes:
		node_type = node.type()
		parent = node.parentNode()

		# --- Check for excluding charactertics
		if node_type == "clonelayer":
			# Process later
			continue
		elif (parent in selected_nodes or parent == active_node or
			node_type in masks_list or
			node.locked() or
			not node.visible() or
			node_type in exclusion_list_with_masks):
			# Don't move nodes when their parents (masks or groups) are also selected.
			# 	Also skip when their parents are the active node
			#	(won't be in selection list and will never move).
			# Never move masks on their own.
			# Don't move edition locked nodes.
			# Don't move invisble nodes.
			# Don't move nodes in unsupported list (fills, filters etc).
			# Don't move nodes when their parents (masks or groups) are also selected.
			continue

		# Calculate new position based on align mode and boundaries
		x, y = calculate_layer_position(mode, rect, node, node_type, is_moving_clones)

		# --- Process masks and layers in groups
		stack = node.findChildNodes("", True)

		# Node has masks or is a group with children.
		#  Move them with parent regardless of their visibility.
		if len(stack) > 0:
			# Retrieve parent position before move
			p = node.position()
			# Calculate translation done by parent
			translate_x = x - p.x()
			translate_y = y - p.y()

			for child in stack:
				if (child.locked()):
					# Only skip locked layers, move invisible ones
					continue

				pchild = child.position()

				# --- Repeat translation of parent so they move as one
				x = pchild.x() + translate_x
				y = pchild.y() + translate_y
				child.move(x, y)

				# When there are clones in layer selection check if this child node is a source
				# 	and if yes, store translation to apply in child clones calculations.
				if is_moving_clones:
					uid = child.uniqueId()
					if uid in clone_nodes:
						clone_nodes[uid]["move_with_group"] = True
						b = clone_nodes[uid]["real_bounds"]
						# Update properties
						clone_nodes[uid]["position"] = QPoint(x, y)
						clone_nodes[uid]["real_bounds"] = QRect(
								b.x() + translate_x,
								b.y() + translate_y,
								b.width(),
								b.height()
							)
						clone_nodes[uid]["translation_x"] += translate_x
						clone_nodes[uid]["translation_y"] += translate_y

		# -- Store translation done by sources of clone layers in selection
		if is_moving_clones:
			uid = node.uniqueId()
			if uid in clone_nodes:
				p = node.position()
				clone_nodes[uid]["translation_x"] += x - p.x()
				clone_nodes[uid]["translation_y"] += y - p.y()

		# --- Finally move current layer into place
		node.move(x, y)

	# -- Process list of clones in selection by moving them and
	# 	countering translation of sources so they end in correct position.
	if is_moving_clones:
		for uid in clone_nodes:
			entry = clone_nodes[uid]

			# Skip ancestral nodes. They're not clones and have been already moved
			if entry["is_ancestral"]:
				continue

			node = entry["node"]

			# Was already checked for visibility and such when building list,
			# 	no need for additional checks here.

			# Retrieve target coordinates, using original position when there's
			# 	none (node is the first or last, not supposed to move).
			if not entry["move_with_group"]:
				x, y = calculate_layer_position(mode, rect, entry, "clonelayer")
			else:
				x = entry["position"].x()
				y = entry["position"].y()

			# Calculate sources movements. This node must make the inverse
			# 	translation to remain in place and make use of the calculated co.
			translation_x = 0
			translation_y = 0

			for source_uid in entry["ancestors"]:
				translation_x += clone_nodes[source_uid]["translation_x"]
				translation_y += clone_nodes[source_uid]["translation_y"]

			# --- Move any masks with clone node
			p = entry["position"]
			move_masks_with_node(node, x - p.x(), y - p.y())

			# --- Move clone layer
			x = x - translation_x
			y = y - translation_y
			node.move(x, y)

			# Take note of movement to apply to clones of this if needed
			clone_nodes[uid]["translation_x"] += x - p.x()
			clone_nodes[uid]["translation_y"] += y - p.y()

	# Refresh canvas (will lose active layer outline, but it's worth it)
	doc.refreshProjection()
	# When using move() on layers with a visible active outline in canvas
	# the outline won't update with the refresh and the layers themselves
	# will jump to the previous position once moved manually by the user.
	# waitForDone() fixes the coordinates problem. How? It's a mystery ~!
	doc.waitForDone()


def distribute_nodes(placement="horizontal", **params):
	""" Distribute selected layers in a given direction and spacing mode.
		@param placement: horizontal or vertical, default horizontal.
		@param params: spacing (only zero for now) when doing edge-to-edge """

	app = Krita.instance()
	doc = app.activeDocument()
	view =  app.activeWindow().activeView()
	selected_nodes = view.selectedNodes()

	# Derive movement axis from placement
	axis = "vertical" if placement in ("top", "bottom", "v_center", "vertical", "vertical_zero") else "horizontal"
	# Set universal spaced placement mode
	placement = "gaps" if placement in ("vertical", "horizontal") else placement
	# Set spacing mode for new zero spacing (edge-to-edge) mode
	spacing = None if "spacing" not in params else params["spacing"]
	reverse = False if "reverse" not in params else params["reverse"]
	backwards = False
	center = False

	# Trim incompatible types from list
	selected_nodes = [node for node in selected_nodes if node.type() not in exclusion_list_with_masks]

	# List of relevant nodes properties sorted by x, y positions. Layers are
	# 	already checked for visibility, locked status and type and removed here.
	# Structure: [ (x, width) ] or [ (y, height) ]
	nodes_props = sort_selected_layers_positions(selected_nodes, axis)

	nodes_count = len(nodes_props)

	if nodes_count < 2 or nodes_count < 3 and placement != "gaps":
		# Must have at least 3 layers to perform any kind of distribution
		# 	or 2 when doing edge-to-edge.
		return

	# --- Build list of clone nodes
	clone_nodes = [x for x in selected_nodes if x.type() == "clonelayer"]
	# Retrieve clones in groups as well
	for node in selected_nodes:
		clone_nodes += node.findChildNodes("", True, False, "clonelayer")
	partial_clones_list = {}
	for node in clone_nodes:
		partial_clones_list = get_clone_sources(node, selected_nodes, partial_clones_list, [], 0)
	clone_nodes = partial_clones_list

	is_moving_clones = bool(len(clone_nodes))

	start_co = nodes_props[0][1]["bounds"]  # Coord of first element
	end_co = nodes_props[-1][1]["bounds"]  # Left edge

	# --- Calculate spacing of nodes
	# Get combined width or height of elements only, ignoring gaps
	combined_size = 0
	for entry in nodes_props:
		combined_size += entry[1]["size"]

	# Skip first and last elements. They don't need to be moved unless spaces will be removed.
	# 	When removing spaces in edge-to-edge modedecide which node to skip (first or last)
	# 	based on direction.
	nodes_range = (nodes_props[:-1] if reverse else nodes_props[1:]) if spacing is not None else nodes_props[1:-1]

	# Determine correct spacing based on aligning by fixed spacing size or edges
	if placement == "gaps":
		''' Move nodes so their edges touch (method supports custom even spacing too, it's just 0 here) '''
		end_co += nodes_props[-1][1]["size"]  # Takes fill combined width into account
		# Space that will be either just removed from between nodes so they align left/top
		# 	or will be removed then added to the start to align them to the right/bottom.
		excess_space = abs(end_co - start_co) - combined_size
		# Spacing = predetermined spacing or escess of space / nodes - 1 (number of gaps)
		spacing = spacing if spacing is not None else round(excess_space / (len(nodes_props)-1))

		# Either add width of first node when skipping it (align left/top) or
		# 	the space that was removed from the end when aligning to rigth/bottom.
		initial_padding = nodes_props[0][1]["size"] if not reverse else excess_space

		next_co = start_co + initial_padding + spacing
	elif placement in ("left", "top"):
		''' Evenly distribute space while aligning by edges, default direction '''
		# Align by edge = Total width - last el width / number of nodes - 1
		spacing = round(abs(end_co - start_co) / (len(nodes_props) - 1))
		next_co = start_co + spacing
	elif placement in ("right", "bottom"):
		''' Evenly distribute space while aligning by edges, default reversed direction '''
		# Coordinates calculation happens backwards in this case
		backwards = True
		# Full width of combined elements
		total_width = (end_co + nodes_props[-1][1]["size"]) - start_co
		# Working width for co calculation disregards first element
		working_width = total_width - nodes_props[0][1]["size"]
		# Spacing is working width / len - 1
		spacing = round(working_width / (len(nodes_props) - 1))

		# Starting coodinate is total width - working width
		start_co += total_width - working_width

		next_co = start_co + spacing
	else:
		''' Evenly distribute space, aligned by centers '''
		center = True

		# The total width coords will start at the half width of
		# first element and end at half width of last
		# It starts in the middle of the first node
		start_co += nodes_props[0][1]["size"]/2
		# And ends in the middle of the last
		end_co += nodes_props[-1][1]["size"]/2

		# Spacing = total width (from centers) /  number of nodes -1
		spacing = round(abs(end_co - start_co) / (len(nodes_props)-1))
		# Spacing is between centers here, hence to x/y
		# you need to subtract half width
		next_co = start_co + spacing

	# Initialize coordinates with position of first element
	co = start_co

	# --- Move nodes
	for entry in nodes_range:
		o, prop = entry
		p = prop["position"]
		b = prop["bounds"]
		rel_pos = b - p
		idx = prop["idx"]
		alt_p = prop["alt_position"]
		size = prop["size"]

		# --- Get node...
		node = selected_nodes[idx]
		node_type = node.type()
		parent = node.parentNode()

		# --- Check for excluding charactertics
		# Explicitly exlude clone layers from this check

		# Already performed visbility etc checks in sort_selected_layers_positions()
		if node_type != "clonelayer" and (parent in selected_nodes or
			# node_type in relative_layers_list or
			node_type in masks_list or
			node.locked() or
			not node.visible() or
			node_type in exclusion_list_with_masks):
			# Don't move nodes when their parents (masks or groups) are also selected.
			# Never move masks on their own.
			# Don't move edition locked nodes.
			# Don't move invisble nodes.
			# Don't move nodes in unsupported list (fills, filters etc).
			# Only ever move a mask with its parent, never by itself.
			continue

		# Adjust position relative to target
		# position determined by previous element
		co = next_co - rel_pos

		if backwards:
			# When spacing something backwards (right, bottom),
			# discount their full width/height
			co -= size
		elif center:
			# Spacing is between centers here, hence to x/y
			# you need to subtract half width
			co = round(co - size / 2)

		# Prepare next position
		if placement == "gaps":
			next_co += size + spacing
		else:
			next_co += spacing

		# --- Only run clone check to skip here because we need to store coords
		if node_type == "clonelayer":
			# Store target position in dict but don't move yet.
			uid = node.uniqueId()
			clone_nodes[uid]["p"] = p
			clone_nodes[uid]["alt_p"] = alt_p
			clone_nodes[uid]["co"] = co  # Relative move...
			continue

		# --- Process masks and layers in groups
		stack = node.findChildNodes("", True)

		# Node has masks or is a group with children.
		# Move them with parent regardless of their visibility.
		if len(stack) > 0:
			# Calculate translation done by parent
			if axis == "horizontal":
				translate_x = co - p
				translate_y = 0
			else:
				translate_x = 0
				translate_y = co - p

			for child in stack:
				if (child.locked()):
					# Only skip locked layers, move invisible ones
					continue

				pchild = child.position()

				# --- Repeat translation of parent so they move as one
				x = pchild.x() + translate_x
				y = pchild.y() + translate_y
				# Move child the same amount parent moves
				child.move(x, y)

				# When there are clones in layer selection check if this child node is a source
				# 	and if yes, store translation to apply in child clones calculations.
				if is_moving_clones:
					uid = child.uniqueId()
					if uid in clone_nodes:
						clone_nodes[uid]["move_with_group"] = True
						b = clone_nodes[uid]["real_bounds"]
						# Update properties
						clone_nodes[uid]["position"] = QPoint(x, y)
						clone_nodes[uid]["real_bounds"] = QRect(
								b.x() + translate_x,
								b.y() + translate_y,
								b.width(),
								b.height()
							)
						clone_nodes[uid]["translation"] += translate_x if axis == "horizontal" else translate_y

		# When there are clones to be moved check if this node is a source
		# 	and if yes, store translation to apply in child clones calculations.
		if is_moving_clones:
			uid = node.uniqueId()
			if uid in clone_nodes:
				clone_nodes[uid]["translation"] = co - p

		# --- Move node into place
		if axis == "horizontal":
			node.move(co, alt_p)
		else:
			node.move(alt_p, co)

	# --- Process clone layers after their parents already were moved
	if is_moving_clones:
		# Retrieve first and/or last nodes positions when they're clones and
		# 	not supposed to move because they'll not have been saved in loop above.
		if nodes_props[0][1]["type"] == "clonelayer":
			''' First node '''
			# Get properties of first node
			o, prop = nodes_props[0]
			# Find index @ selected_nodes and retrieve node
			node = selected_nodes[prop["idx"]]
			# So uid can be found to select correct node in clone lists
			entry = clone_nodes[node.uniqueId()]

			entry["p"] = prop["position"]
			# Sometimes co will have been saved when working with gaps
			# 	and it'll not be the original position.
			entry["co"] = entry.get("co", entry["p"])
			entry["alt_p"] = prop["alt_position"]

		if nodes_props[-1][1]["type"] == "clonelayer":
			''' Last node '''
			o, prop = nodes_props[-1]
			node = selected_nodes[prop["idx"]]
			entry = clone_nodes[node.uniqueId()]

			entry["p"] = prop["position"]
			entry["co"] = entry.get("co", entry["p"])
			entry["alt_p"] = prop["alt_position"]

		for uid in clone_nodes:
			entry = clone_nodes[uid]

			# Skip ancestral nodes. They're not clones and have been already moved.
			if entry["is_ancestral"]:
				continue

			node = entry["node"]

			# Was already checked for visibility and such when building list,
			# 	no need for additional checks here.

			# A non-selected source or child in group won't have a target co,
			# 	they should only have their original positions restored.
			if "co" not in entry:
				if axis == "horizontal":
					entry["p"] = entry["co"] = entry["position"].x()
					entry["alt_p"] = entry["position"].y()
				else:
					entry["p"] = entry["co"] = entry["position"].y()
					entry["alt_p"] = entry["position"].x()


			co = entry["co"]
			alt_p = entry["alt_p"]

			# Calculate sources movements. This node must make the inverse
			# 	translation to remain in place and make use of the calculated co.
			translation = 0

			for source_uid in entry["ancestors"]:
				# translation += clone_nodes[source_uid]["translation"] if source_uid in clone_nodes else 0
				translation += clone_nodes[source_uid]["translation"]


			# Apply sources' translations to node movement
			co = co - translation
			translation_x = translation_y = 0
			if axis == "horizontal":
				x = co
				y = alt_p
				translation_x += translation
			else:
				x = alt_p
				y = co
				translation_y += translation

			# --- Move any masks with clone node
			translation_x += x - entry["position"].x()
			translation_y += y - entry["position"].y()
			move_masks_with_node(node, translation_x, translation_y)

			# --- Move clone
			node.move(x, y)

			# Take note of movement to apply to clones of this if needed
			clone_nodes[uid]["translation"] += co - entry["p"]

	# Refresh canvas (will lose active layer outline, but it's worth it)
	doc.refreshProjection()
	# When using move() on layers with a visible active outline in canvas
	# the outline won't update with the refresh and the layers themselves
	# will jump to the previous position once moved manually by the user.
	# waitForDone() fixes the coordinates problem. How? It's a mystery ~!
	doc.waitForDone()


######################## Operator Utils ##########################

def calculate_group_bounds(stack):
	""" Calculate bounds of group of layers in stack, correcting for clones bounds.
		@param stack list of layers.
		@return QRect bounds of group of layers. """
	# Dummy values for comparisions
	inf = float('inf')
	rect = {
		"x": inf, "y": inf,  # Min position
		"x_out": -inf, "y_out": -inf,  # Max position
	}

	for node in stack:
		node_type = node.type()
		if node_type in exclusion_list_with_masks:
			# Skip masks and boundless layer types (fill, filter, ...)
			# 	They don't have dimensions to contribute to size.
			continue

		# BUG FIX: A hopefully temporary fix for clone layer buggy bounds.
		b = node.bounds() if node_type != "clonelayer" else correct_clone_bounds(node, node.bounds(), node.position())

		# Starting coordinates will be the lowest x/y
		rect["x"] = min(rect["x"], b.x())
		rect["y"] = min(rect["y"], b.y())
		# Get outer bounds by comparing right/bottom edges of elements
		rect["x_out"] = max(rect["x_out"], b.x() + b.width())
		rect["y_out"] = max(rect["y_out"], b.y() + b.height())

	# Build boundaries, subtracting positional coords from width and height
	rect = QRect(
		rect["x"],
		rect["y"],
		rect["x_out"] - rect["x"],
		rect["y_out"] - rect["y"]
	)

	return rect


def calculate_layer_position(mode, rect, node, node_type=None, contains_clones=False):
	""" Calculate given a node new position relative to rect.
		@param mode Direction of alignment.
		@param rect QRect to which layers will be aligned.
		@param node Layer for which new position is being calculated
		@param node_type Only relevant for clone layers (BUG FIX), default None.
		@param contains_clones Flag to fix bounds of group layers that could contain clone layers, default False.
		@return Target position for alignment. """

	if contains_clones and node_type == "grouplayer":
		''' Group layers in a layer selection containing clones '''
		stack = node.findChildNodes("", True)
		p = node.position()
		# BUG FIX: Fix bounds of groups with clone children >(
		b = calculate_group_bounds(stack)
	elif node_type != "clonelayer":
		''' Regular layers that aren't evil '''
		b = node.bounds()
		p = node.position()
	else:
		''' Clone layers are special (and evil) '''
		entry = node
		node = entry["node"]
		# BUG FIX: Use fixed bounds calculated before any movement happend.
		# 	Because sometimes the doc updates bounds in the middle
		# 	of math (breaking formulas!), sometimes it doesn't.
		b = entry["real_bounds"]
		p = entry["position"]
		# b = correct_clone_bounds(node, b, p)

	pos_x, pos_y = (b.x() - p.x()), (b.y() - p.y())

	if mode == "left":
		return (rect.x() - pos_x, p.y())
	elif mode == "right":
		return ( (rect.x() - pos_x) + (rect.width() - b.width()), p.y())
	elif mode == "top":
		return (p.x(), rect.y() - pos_y)
	elif mode == "bottom":
		return (p.x(), ((rect.y() + rect.height()) - b.height() ) - pos_y)
	elif mode == "v_center":
		return (p.x(), rect.y() +  round(( rect.height() - b.height() )/2) - pos_y)
	elif mode == "h_center":
		return (rect.x() + round(( rect.width() - b.width() )/2) - pos_x, p.y())


def sort_selected_layers_positions(selected_nodes, axis="x", gaps=False):
	""" Return a list of layers containing their properties ordered by their positions.
		@param selected_nodes: List of selected layers.
		@param axis: Axis being sorted, default x.
		@return: List of layers sorted by position. """

	# "Positions" here should be understood as bounds x and y. Bounds are relative to the
	# 	canvas origin. To protect our sanity we're using them.

	nodes_list = {}
	sorted_positions = {}

	for idx, node in enumerate(selected_nodes):
		node_type = node.type()
		parent = node.parentNode()

		if (node_type in exclusion_list or
			node.locked() or
			not node.visible() or
			node_type in exclusion_list_with_masks):
			# Skip masks.
			# Skip edition locked nodes.
			# Skip invisble nodes.
			# Skip nodes in unsupported list (fills, filters etc).
			continue

		b = node.bounds()
		p = node.position()

		# Order by bounds x or y
		sorting_x = b_x = b.x()
		sorting_y = b_y = b.y()
		# Extra data
		p_x = p.x()
		p_y = p.y()

		if node_type == "clonelayer" and parent not in selected_nodes:
			# --- BUG FIX: Fix clone bad bounds, but only clones not in group
			b = correct_clone_bounds(node, b, p)
			sorting_x = b_x = b.x()
			sorting_y = b_y = b.y()
		elif node_type == "grouplayer":
			# Unfortunately groups may also contain clones, they need
			# 	correction too, but as a whole.
			stack = node.findChildNodes("", True)
			b = calculate_group_bounds(stack)
			sorting_x = b_x = b.x()
			sorting_y = b_y = b.y()
		elif parent in selected_nodes: # Should this be here?
			# Don't move nodes when their parents (masks or groups) are also selected
			continue

		width = b.width()
		height = b.height()
		rel_pos_x = b_x - p_x
		rel_pos_y = b_y - p_y

		# Keeping naming conventions starndard so code doesn't
		# need to be written for ["width"], ["height"]

		# Create sublist of node indexes ordered by position to be sorted later.
		# Necessary because multiple nodes may have same position,
		# 	so a plain dict ordered by position won't do.
		''' Structure sorted_positions:
		{
			coordinates (int: x or y) :
				[
					idx (int: index @ selected nodes),
					(...)
				],
			(...) : { ... }
		}
		Structure nodes_list (unsorted):
		{
			idx (int: index @ selected nodes) :
				{
					size: (int: width or height),
					idx: (int: index @ selected_nodes),
					position: (int: node.position() x or y),
					alt_position: (int: node.position() x or y, axis that won't move),
					bounds: (int: node.bounds() x or y),
					name: (str: debug)
				},
			(...) : { ... }
		}
		'''
		if axis == "horizontal":
			# Positions list
			sorted_positions[sorting_x] = sorted_positions.get(sorting_x, [])
			sorted_positions[sorting_x].append(idx)
			# Props
			nodes_list[idx] = ({
				"size": width,
				"idx": idx,
				"type": node_type,
				"position": p_x,
				"bounds": b_x,
				"alt_position": p_y  # To complete move parameters
			})
		else:
			# Positions list
			sorted_positions[sorting_y] = sorted_positions.get(sorting_y, [])
			sorted_positions[sorting_y].append(idx)
			# Props
			nodes_list[idx] = ({
				"size": height,
				"idx": idx,
				"type": node_type,
				"position": p_y,
				"bounds": b_y,
				"alt_position": p_x
			})

	# Order by position
	sorted_positions = sorted(sorted_positions.items())

	# Finally, re-structure the list
	nodes_by_position = {}
	for item in sorted_positions:
		data = item[1]
		for idx in data:
			nodes_by_position[idx] = nodes_list[idx]

	# Convert to list so elements can be selected by their positions on list
	nodes_by_position = list(nodes_by_position.items())


	''' Final structure:
		[
		(
			idx (int: index @ selected nodes) :
				{
					size: (int: width or height),
					idx: (int: index @ selected_nodes),
					position: (int: node.position() x or y),
					alt_position: (int: node.position() x or y, axis that won't move),
					bounds: (int: node.bounds() x or y),
					name: (str: debug)
				}
		),
		(... , ...)
	]
	'''

	return nodes_by_position

def move_masks_with_node(parent_node, translate_x, translate_y):
	""" Process masks of a given node (clone only for now) """
	stack = parent_node.findChildNodes("", True)

	# Move masks with parent regardless of their visibility
	for child in stack:
		if (child.locked()):
			# Only skip locked layers, move invisible ones
			continue

		pchild = child.position()

		# --- Repeat translation of parent so they move as one
		x = pchild.x() + translate_x
		y = pchild.y() + translate_y
		child.move(x, y)

######################## Clone Layer Methods ##########################

def get_clone_sources(clone_node, selected_nodes, sources_list={}, ancestors=[], descendant_level=0):
	""" Recusive method to get a clone's sources list, sorted from source to child, no duplicates.
		@param clone_node: Clone node for which source is being retrieved.
		@param selected_nodes: List of selected layers.
		@param sources_list: List containg all sources found, sorted by seniority.
		@param ancestors: List of ancestors (layer uniqueIds) of this layer.
		@param descendant_level: How far up the descendant tree this layer is.
		@return: sources_list """

	source = clone_node.sourceNode()
	uid = clone_node.uniqueId()
	suid = source.uniqueId()
	if suid not in ancestors:
		ancestors.append(suid)

	# Always investigate full source chain in case some are in selection
	if source.type() == "clonelayer":
		# Add to desdants level while it's recursive.
		descendant_level += 1
		# Inception!
		sources_list = get_clone_sources(source, selected_nodes, sources_list, ancestors, descendant_level)
		# Recursion ended, start removing levels. We're climbing back up the ancestor tree now.
		descendant_level -= 1

	elif uid not in sources_list:
		# Always append major ancestors
		sources_list[suid] = {
			"node" : source,
			"bounds" : source.bounds(),  # Align nodes
			"is_ancestral" : True,
			"translation" : 0,  # Distribute nodes
			"translation_x" : 0,  # Align nodes
			"translation_y" : 0,
			"ancestors" : None

		}

	if uid not in sources_list:
		# Is a layer being moved.
		# Not yet on sources list.
		# Editable and visible.
		# Store node, position and bounds (for dimensions)

		# Store position, calculate fixed bounds at this point to ensure
		# 	the properties used aren't affected by any source's movement.
		# 	Because sometimes the doc updates clones bounds in the middle of math,
		# 	sometimes it doesn't. WHY you'd do that to me Krita?! <o>

		sources_list[uid] = {
			"node" : clone_node,
			"position" : clone_node.position(),  # Align nodes
			# BUG FIX for clone bounds
			"real_bounds" : correct_clone_bounds(clone_node, clone_node.bounds(), clone_node.position()),
			"bounds" : source.bounds(), # obsolete
			"is_ancestral" : False,
			"move_with_group": False,
			"translation" : 0,  # Distribute nodes
			"translation_x" : 0,  # Align nodes
			"translation_y" : 0,
			"ancestors" : ancestors[descendant_level:], # Remove descendants not belonging to this lvl

		}

	return sources_list


def correct_clone_bounds(node, b=None, p=None):
	""" Retrieve corrected clone layer bounds for positioning calculations.
		@param node: Clone layer being corrected.
		@param b: Bounds if it was already retrieved, default None.
		@param p: Position if it was already retrieved, default None.
		@return: Corrected layer bounds (QRect). """
	b = b or node.bounds()
	p = p or node.position()

	# BUG FIX: Clone layers positions are relative to their source layers, however:
	# 	- As of 5.2.2 bounds are buggy. They don't inform the actual layer
	# 	boundaries nor their correct dimensions.
	# 	- Their sources might be clone layers themselves, also making these
	# 	sources relative to their sources, which can also be relative...
	# 	When a source moves any clones and clones of clones will move. It's easier
	# 	to account for that movement during align or distribution operations than
	# 	to try to calculate the layers relativity here.

	# Extract data
	width, height = b.width(), b.height()
	b_x, b_y = b.x(), b.y()
	p_x, p_y = p.x(), p.y()

	# --- Correct bounds bug. IMPORTANT: Might be removed if their calculation method is fixed!
	# Dimensions are always wrong
	width = width - abs(p_x)
	height = height - abs(p_y)
	# Bounds coordinates are correct when position is negative, but not when positive
	if p_x > 0:
		b_x = p_x + b_x
	if p_y > 0:
		b_y = p_y + b_y

	# Recreate bounds for calculations
	b = QRect(b_x, b_y, width, height)

	return b
