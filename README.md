# Arrange 2
Arrange 2 extends the functionality of Krita’s standard arrange tools for vector layers, adding support to aligning and distributing a mix all of types of layers.

### Changelog

**Version 1.0.0** (07-08-2024)
Initial release.

## Installation
1. Copy the `Arrange2` folder and `arrange2.desktop` to the `pykrita` directory found in your **Krita resources folder**.
2. Start Krita and enable the plugin at: `Settings > Configure Krita... > Python Plugin Manager`
3. Restart Krita.
4. Enable the `Arrange` docker.

## How to Use
The alignment and distribution tools will appear on the old `Arrange` docker.

By default Krita will activate the `Select Shapes Tool` when you select a vector layer. That will display the old Arrange docker contents so you can arrange shapes within a same vector layer. To use the new tools you'll need to select any other tool, like the `Move` tool.

## Features
- It supports all kinds of layers, including groups.
- You can choose to align elements to the **Active Layer**, the **Canvas** or all **Selected Layers**.
- Elements are distributed according to their coordinates on canvas, not their Z order like Krita's arrange for vectors.
- There are four new `Edge-to-edge` distribution modes. They were added to make it easier to place elements side-by-side without any spaces, making up for the current lack of snapping to edges when moving layers. It's very helpful when creating layouts, presentations for clients showing design options, step-by-step progressions and more.
- The plugin also patches a minor bug in which when the original Arrange docker gets initialized it would change the height of the docker, squeezing other dockers. Now it's more well behaved with a smaller minimum height.

#### Layer Types Support
Some layers types like fills don't have dimensions, beginning or end. In this case they're only supported in some operations under specific circumstances.

|Layer Type | Directly Selected | Parent / Source Selected | Align | Distribute  |  Notes |
|--- | --- | ---| --- | --- | ---|
|Paint Layer | Yes | Y/N  | :white_check_mark: | :white_check_mark: | Won't move when hidden or with edition lock.|
|Vector Layer | Yes | Y/N  | :white_check_mark: | :white_check_mark: | Won't move when hidden or with edition lock.|
|Colorize Layer | Yes | Y/N  | :white_check_mark: | :white_check_mark: | Won't move when hidden or with edition lock.|
|Clone Layer| Yes | Y/N | :white_check_mark: | :white_check_mark: | Won't move when hidden or with edition lock. If it's a source to another clone it'll also move.|
|Clone Layer|  No :warning: | Y/N | :white_check_mark:* | :white_check_mark:* | Clones of layers being moved will also move because they're relative to them. Their positions won't be corrected unless they're also being moved by being directly selected or are inside a group being moved. |
|Group Layer | Yes | Y/N | :white_check_mark: | :white_check_mark: | When a group is selected its children layers will move as a single unit. Hidden layers will also move, but layers with edition lock won't.|
| Layers Inside Group | Yes :warning: | No | :white_check_mark: | :white_check_mark: | When the parent group isn't selected layers will move individually. |
|Fill / Filter Layer | Y/N | Yes | :white_check_mark: | :white_check_mark: | Will move with parent group. |
|Fill / Filter Layer | Yes | No :warning: | :white_check_mark:* | :x: | The layer won't move without a parent. When it's the `Active Layer` during alignments the selected layers will align to the canvas instead. |
|Masks| Yes :warning:  | Y/N | :white_check_mark:* | :white_check_mark:*  | Move when inside groups or together with a parent layer. Will move even when hidden, but not edition locked.|
|Masks| No :warning: | Yes | :x: | :x: | Can't be moved on their own. |


### Limitations
- You can't redo and undo Arrange 2 actions because they aren't part of the layer history.
- Arranging or distributing layers outside the canvas bounds may because they don't inform their dimensions or positions relative to the canvas.

## Compatibility

This plugin was last tested on Krita 5.2.2. It should keep working until Krita's next major release at the very least.
That happens because the menu entries don't exist while the window is being created, only after, so they can be only altered when the window is already visible.
