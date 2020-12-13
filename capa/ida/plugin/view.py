# Copyright (C) 2020 FireEye, Inc. All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
# You may obtain a copy of the License at: [package root]/LICENSE.txt
# Unless required by applicable law or agreed to in writing, software distributed under the License
#  is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

import idc
from PyQt5 import QtCore, QtWidgets

from capa.ida.plugin.item import CapaExplorerFunctionItem
from capa.ida.plugin.model import CapaExplorerDataModel

MAX_SECTION_SIZE = 750


class CapaExplorerQtreeView(QtWidgets.QTreeView):
    """tree view used to display hierarchical capa results

    view controls UI action responses and displays data from CapaExplorerDataModel

    view does not modify CapaExplorerDataModel directly - data modifications should be implemented
    in CapaExplorerDataModel
    """

    def __init__(self, model, parent=None):
        """initialize view"""
        super(CapaExplorerQtreeView, self).__init__(parent)

        self.setModel(model)

        self.model = model
        self.parent = parent

        # control when we resize columns
        self.should_resize_columns = True

        # configure custom UI controls
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.setExpandsOnDoubleClick(False)
        self.setSortingEnabled(True)
        self.model.setDynamicSortFilter(False)

        # configure view columns to auto-resize
        for idx in range(CapaExplorerDataModel.COLUMN_COUNT):
            self.header().setSectionResizeMode(idx, QtWidgets.QHeaderView.Interactive)

        # disable stretch to enable horizontal scroll for last column, when needed
        self.header().setStretchLastSection(False)

        # connect slots to resize columns when expanded or collapsed
        self.expanded.connect(self.slot_resize_columns_to_content)
        self.collapsed.connect(self.slot_resize_columns_to_content)

        # connect slots
        self.customContextMenuRequested.connect(self.slot_custom_context_menu_requested)
        self.doubleClicked.connect(self.slot_double_click)

        self.setStyleSheet("QTreeView::item {padding-right: 15 px;padding-bottom: 2 px;}")

    def reset_ui(self, should_sort=True):
        """reset user interface changes

        called when view should reset UI display e.g. expand items, resize columns

        @param should_sort: True, sort results after reset, False don't sort results after reset
        """
        if should_sort:
            self.sortByColumn(CapaExplorerDataModel.COLUMN_INDEX_RULE_INFORMATION, QtCore.Qt.AscendingOrder)

        self.should_resize_columns = False
        self.expandToDepth(0)
        self.should_resize_columns = True

        self.slot_resize_columns_to_content()

    def slot_resize_columns_to_content(self):
        """reset view columns to contents"""
        if self.should_resize_columns:
            self.header().resizeSections(QtWidgets.QHeaderView.ResizeToContents)

            # limit size of first section
            if self.header().sectionSize(0) > MAX_SECTION_SIZE:
                self.header().resizeSection(0, MAX_SECTION_SIZE)

    def map_index_to_source_item(self, model_index):
        """map proxy model index to source model item

        @param model_index: QModelIndex

        @retval QObject
        """
        # assume that self.model here is either:
        #  - CapaExplorerDataModel, or
        #  - QSortFilterProxyModel subclass
        #
        # The ProxyModels may be chained,
        #  so keep resolving the index the CapaExplorerDataModel.

        model = self.model
        while not isinstance(model, CapaExplorerDataModel):
            if not model_index.isValid():
                raise ValueError("invalid index")

            model_index = model.mapToSource(model_index)
            model = model.sourceModel()

        if not model_index.isValid():
            raise ValueError("invalid index")

        return model_index.internalPointer()

    def send_data_to_clipboard(self, data):
        """copy data to the clipboard

        @param data: data to be copied
        """
        clip = QtWidgets.QApplication.clipboard()
        clip.clear(mode=clip.Clipboard)
        clip.setText(data, mode=clip.Clipboard)

    def new_action(self, display, data, slot):
        """create action for context menu

        @param display: text displayed to user in context menu
        @param data: data passed to slot
        @param slot: slot to connect

        @retval QAction
        """
        action = QtWidgets.QAction(display, self.parent)
        action.setData(data)
        action.triggered.connect(lambda checked: slot(action))

        return action

    def load_default_context_menu_actions(self, data):
        """yield actions specific to function custom context menu

        @param data: tuple

        @yield QAction
        """
        default_actions = (
            ("Copy column", data, self.slot_copy_column),
            ("Copy row", data, self.slot_copy_row),
        )

        # add default actions
        for action in default_actions:
            yield self.new_action(*action)

    def load_function_context_menu_actions(self, data):
        """yield actions specific to function custom context menu

        @param data: tuple

        @yield QAction
        """
        function_actions = (("Rename function", data, self.slot_rename_function),)

        # add function actions
        for action in function_actions:
            yield self.new_action(*action)

        # add default actions
        for action in self.load_default_context_menu_actions(data):
            yield action

    def load_default_context_menu(self, pos, item, model_index):
        """create default custom context menu

        creates custom context menu containing default actions

        @param pos: cursor position
        @param item: CapaExplorerDataItem
        @param model_index: QModelIndex

        @retval QMenu
        """
        menu = QtWidgets.QMenu()

        for action in self.load_default_context_menu_actions((pos, item, model_index)):
            menu.addAction(action)

        return menu

    def load_function_item_context_menu(self, pos, item, model_index):
        """create function custom context menu

        creates custom context menu with both default actions and function actions

        @param pos: cursor position
        @param item: CapaExplorerDataItem
        @param model_index: QModelIndex

        @retval QMenu
        """
        menu = QtWidgets.QMenu()

        for action in self.load_function_context_menu_actions((pos, item, model_index)):
            menu.addAction(action)

        return menu

    def show_custom_context_menu(self, menu, pos):
        """display custom context menu in view

        @param menu: QMenu to display
        @param pos: cursor position
        """
        if menu:
            menu.exec_(self.viewport().mapToGlobal(pos))

    def slot_copy_column(self, action):
        """slot connected to custom context menu

        allows user to select a column and copy the data to clipboard

        @param action: QAction
        """
        _, item, model_index = action.data()
        self.send_data_to_clipboard(item.data(model_index.column()))

    def slot_copy_row(self, action):
        """slot connected to custom context menu

        allows user to select a row and copy the space-delimited data to clipboard

        @param action: QAction
        """
        _, item, _ = action.data()
        self.send_data_to_clipboard(str(item))

    def slot_rename_function(self, action):
        """slot connected to custom context menu

        allows user to select a edit a function name and push changes to IDA

        @param action: QAction
        """
        _, item, model_index = action.data()

        # make item temporary edit, reset after user is finished
        item.setIsEditable(True)
        self.edit(model_index)
        item.setIsEditable(False)

    def slot_custom_context_menu_requested(self, pos):
        """slot connected to custom context menu request

        displays custom context menu to user containing action relevant to the item selected

        @param pos: cursor position
        """
        model_index = self.indexAt(pos)

        if not model_index.isValid():
            return

        item = self.map_index_to_source_item(model_index)

        column = model_index.column()
        menu = None

        if CapaExplorerDataModel.COLUMN_INDEX_RULE_INFORMATION == column and isinstance(item, CapaExplorerFunctionItem):
            # user hovered function item
            menu = self.load_function_item_context_menu(pos, item, model_index)
        else:
            # user hovered default item
            menu = self.load_default_context_menu(pos, item, model_index)

        # show custom context menu at view position
        self.show_custom_context_menu(menu, pos)

    def slot_double_click(self, model_index):
        """slot connected to double-click event

        if address column clicked, navigate IDA to address, else un/expand item clicked

        @param model_index: QModelIndex
        """
        if not model_index.isValid():
            return

        item = self.map_index_to_source_item(model_index)
        column = model_index.column()

        if CapaExplorerDataModel.COLUMN_INDEX_VIRTUAL_ADDRESS == column and item.location:
            # user double-clicked virtual address column - navigate IDA to address
            idc.jumpto(item.location)

        if CapaExplorerDataModel.COLUMN_INDEX_RULE_INFORMATION == column:
            # user double-clicked information column - un/expand
            self.collapse(model_index) if self.isExpanded(model_index) else self.expand(model_index)
