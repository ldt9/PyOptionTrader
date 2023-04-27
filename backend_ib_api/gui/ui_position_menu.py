#!/usr/bin/env python
# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets, QtGui
from datetime import datetime
from ..order.order_type import OrderType
from ..order.order_event import OrderEvent
from ..event.event import LogEvent
import logging

_logger = logging.getLogger(__name__)


class PositionMenuBottom(QtWidgets.QTableWidget):
    def __init__(self, strategy_manager, parent=None):
        super(PositionMenuBottom, self).__init__(parent)

        self.strategy_manager = strategy_manager

        self.header = ['SID',
                       'Symbol',
                       'Size',
                       'AvgPrice',
                       'OpenPnL',
                       'ClosePnL']
        self.init_table(0)

    def create_table(self, sid):
        self.setRowCount(0)       # delete all rows
        if sid == 0:
            pos_manager = self. strategy_manager._position_manager
        else:
            pos_manager = self. strategy_manager._strategy_dict[sid]._position_manager

        for sym, pos in pos_manager.positions.items():
            try:
                self.insertRow(self.rowCount())
                self.setItem(self.rowCount() - 1, 0, QtWidgets.QTableWidgetItem(str(sid)))
                self.setItem(self.rowCount() - 1, 1, QtWidgets.QTableWidgetItem(sym))
                self.setItem(self.rowCount() - 1, 2, QtWidgets.QTableWidgetItem(str(pos.size)))
                self.setItem(self.rowCount() - 1, 3, QtWidgets.QTableWidgetItem(str(pos.average_price)))
                self.setItem(self.rowCount() - 1, 4, QtWidgets.QTableWidgetItem(str(pos.unrealized_pnl)))
                self.setItem(self.rowCount() - 1, 5, QtWidgets.QTableWidgetItem(str(pos.realized_pnl)))
            except:
                pass

    def init_table(self, sid):
        col = len(self.header)
        self.setColumnCount(col)

        self.setHorizontalHeaderLabels(self.header)
        self.setEditTriggers(self.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)

        self.create_table(sid)


class PositionMenu(QtWidgets.QWidget):
    def __init__(self, staretgy_manager):
        super(PositionMenu, self).__init__()

        self.strategy_manager = staretgy_manager
        self.bottom_table = None

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Strategy Positions')
        self.setWindowIcon(QtGui.QIcon("gui/image/logo.ico"))
        self.resize(800, 500)

        hbox = QtWidgets.QHBoxLayout()
        top = QtWidgets.QFrame()
        top.setFrameShape(QtWidgets.QFrame.StyledPanel)
        control_layout = QtWidgets.QHBoxLayout()
        self.strategy_List = QtWidgets.QComboBox()
        self.strategy_List.addItems([str(i) for i in range(len(self.strategy_manager._strategy_dict)+1)])
        control_layout.addWidget(self.strategy_List)
        self.btn_refresh = QtWidgets.QPushButton('Refresh')
        self.btn_refresh.clicked.connect(self.refresh_position)
        control_layout.addWidget(self.btn_refresh)
        top.setLayout(control_layout)

        bottom = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout()
        self.bottom_table = PositionMenuBottom(self.strategy_manager)
        bottom_layout.addWidget(self.bottom_table)
        bottom.setLayout(bottom_layout)

        splitter1 = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter1.addWidget(top)
        splitter1.addWidget(bottom)
        hbox.addWidget(splitter1)
        self.setLayout(hbox)

    def refresh_position(self):
        sid = self.strategy_List.currentIndex()
        _logger.info(f'Position refreshed for SID {sid}')
        self.bottom_table.create_table(int(sid))