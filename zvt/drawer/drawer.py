# -*- coding: utf-8 -*-
import os
from typing import List, Optional

import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots

from zvt import zvt_env
from zvt.contract.api import decode_entity_id
from zvt.contract.normal_data import NormalData
from zvt.utils.pd_utils import pd_is_not_null
from zvt.utils.time_utils import now_time_str, TIME_FORMAT_ISO8601


class Rect(object):

    def __init__(self, x0, y0, x1, y1) -> None:
        self.x0 = x0
        self.x1 = x1
        self.y0 = y0
        self.y1 = y1


class Drawable(object):

    def draw(self, width=None, height=None, title=None, keep_ui_state=True, show=False, **kwargs):
        drawer = Drawer(main_df=self.drawer_main_df(),
                        main_data=self.drawer_main_data(),
                        factor_df_list=self.drawer_factor_df_list(),
                        factor_data_list=self.drawer_factor_data_list(),
                        sub_df=self.drawer_sub_df(),
                        sub_data=self.drawer_sub_data(),
                        annotation_df=self.drawer_annotation_df(),
                        rects=self.drawer_rects())

        return drawer.draw_kline(width=width, height=height, title=title, keep_ui_state=keep_ui_state, show=show,
                                 **kwargs)

    def drawer_main_df(self) -> Optional[pd.DataFrame]:
        return None

    def drawer_main_data(self) -> Optional[NormalData]:
        return None

    def drawer_factor_df_list(self) -> Optional[List[pd.DataFrame]]:
        return None

    def drawer_factor_data_list(self) -> Optional[List[NormalData]]:
        return None

    def drawer_sub_df(self) -> Optional[pd.DataFrame]:
        return None

    def drawer_sub_data(self) -> Optional[NormalData]:
        return None

    def drawer_annotation_df(self) -> Optional[pd.DataFrame]:
        return None

    def drawer_rects(self) -> List[Rect]:
        return None


class Drawer(object):
    def __init__(self,
                 main_df: pd.DataFrame = None,
                 factor_df_list: List[pd.DataFrame] = None,
                 sub_df: pd.DataFrame = None,
                 main_data: NormalData = None,
                 factor_data_list: List[NormalData] = None,
                 sub_data: NormalData = None,
                 rects: List[Rect] = None,
                 annotation_df: pd.DataFrame = None) -> None:
        """

        :param main_df: df for main chart
        :param factor_df_list: list of factor df on main chart
        :param sub_df: df for sub chart under main chart
        :param main_data: NormalData wrap main_df,use either
        :param factor_data_list: list of NormalData wrap factor_df,use either
        :param sub_data: NormalData wrap sub_df,use either
        :param annotation_df:
        """

        # 主图数据
        if main_data is None:
            main_data = NormalData(main_df)
        self.main_data: NormalData = main_data

        # 主图因子
        if not factor_data_list and factor_df_list:
            factor_data_list = []
            for df in factor_df_list:
                factor_data_list.append(NormalData(df))
        self.factor_data_list: NormalData = factor_data_list

        # 副图数据
        if sub_data is None:
            sub_data = NormalData(sub_df)
        self.sub_data: NormalData = sub_data

        # 主图的标记数据
        self.annotation_df = annotation_df

        # [((x,y),(x1,y1))]
        self.rects = rects

    def _draw(self,
              main_chart='kline',
              sub_chart='bar',
              mode='lines',
              width=None,
              height=None,
              title=None,
              keep_ui_state=True,
              show=False,
              **kwargs):
        if self.sub_data is not None and not self.sub_data.empty():
            subplot = True
            fig = make_subplots(rows=2, cols=1, row_heights=[0.8, 0.2], vertical_spacing=0.08, shared_xaxes=True)
            sub_traces = []
        else:
            subplot = False
            fig = go.Figure()

        traces = []

        for entity_id, df in self.main_data.entity_map_df.items():
            code = entity_id
            try:
                _, _, code = decode_entity_id(entity_id)
            except Exception:
                pass

            # 绘制主图
            if main_chart == 'kline':
                trace_name = '{}_kdata'.format(code)
                trace = go.Candlestick(x=df.index, open=df['open'], close=df['close'], low=df['low'], high=df['high'],
                                       name=trace_name, **kwargs)
                traces.append(trace)
            elif main_chart == 'scatter':
                for col in df.columns:
                    trace_name = '{}_{}'.format(code, col)
                    ydata = df[col].values.tolist()
                    traces.append(go.Scatter(x=df.index, y=ydata, mode=mode, name=trace_name, **kwargs))

            # 绘制主图指标
            if self.factor_data_list:
                for factor_data in self.factor_data_list:
                    factor_df = factor_data.entity_map_df.get(entity_id)
                    if pd_is_not_null(factor_df):
                        for col in factor_df.columns:
                            trace_name = '{}_{}'.format(code, col)
                            ydata = factor_df[col].values.tolist()

                            line = go.Scatter(x=factor_df.index, y=ydata, mode=mode, name=trace_name, **kwargs)
                            traces.append(line)

            # 绘制幅图
            if subplot:
                sub_df = self.sub_data.entity_map_df.get(entity_id)
                if pd_is_not_null(sub_df):
                    for col in sub_df.columns:
                        trace_name = '{}_{}'.format(code, col)
                        ydata = sub_df[col].values.tolist()

                        def color(i):
                            if i > 0:
                                return 'red'
                            else:
                                return 'green'

                        colors = [color(i) for i in ydata]

                        if sub_chart == 'line':
                            sub_trace = go.Scatter(x=sub_df.index, y=ydata, name=trace_name, yaxis='y2',
                                                   marker_color=colors)
                        else:
                            sub_trace = go.Bar(x=sub_df.index, y=ydata, name=trace_name, yaxis='y2',
                                               marker_color=colors)
                        sub_traces.append(sub_trace)

        if subplot:
            fig.add_traces(traces, rows=[1] * len(traces), cols=[1] * len(traces))
            fig.add_traces(sub_traces, rows=[2] * len(sub_traces), cols=[1] * len(sub_traces))
        else:
            fig.add_traces(traces)

        fig.layout = self.gen_plotly_layout(width=width, height=height, title=title, keep_ui_state=keep_ui_state,
                                            subplot=subplot)

        # 绘制矩形
        if self.rects:
            for rect in self.rects:
                fig.add_shape(type="rect",
                              x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1,
                              line=dict(
                                  color="RoyalBlue",
                                  width=2),
                              fillcolor="LightSkyBlue")
            fig.update_shapes(dict(xref='x', yref='y'))

        if show:
            fig.show()
        else:
            return fig

    def draw_kline(self, width=None, height=None, title=None, keep_ui_state=True, show=False, **kwargs):
        return self._draw('kline', width=width, height=height, title=title, keep_ui_state=keep_ui_state, show=show,
                          **kwargs)

    def draw_line(self, width=None, height=None, title=None, keep_ui_state=True, show=False, **kwargs):
        return self.draw_scatter(mode='lines', width=width, height=height, title=title,
                                 keep_ui_state=keep_ui_state, show=show, **kwargs)

    def draw_area(self, width=None, height=None, title=None, keep_ui_state=True, show=False, **kwargs):
        return self.draw_scatter(mode='none', width=width, height=height, title=title,
                                 keep_ui_state=keep_ui_state, show=show, **kwargs)

    def draw_scatter(self, mode='markers', width=None, height=None,
                     title=None, keep_ui_state=True, show=False, **kwargs):
        return self._draw('scatter', mode=mode, width=width, height=height, title=title, keep_ui_state=keep_ui_state,
                          show=show, **kwargs)

    def draw_table(self, width=None, height=None, title=None, keep_ui_state=True, **kwargs):
        cols = self.main_data.data_df.index.names + self.main_data.data_df.columns.tolist()

        index1 = self.main_data.data_df.index.get_level_values(0).tolist()
        index2 = self.main_data.data_df.index.get_level_values(1).tolist()
        values = [index1] + [index2] + [self.main_data.data_df[col] for col in self.main_data.data_df.columns]

        data = go.Table(
            header=dict(values=cols,
                        fill_color=['#000080', '#000080'] + ['#0066cc'] * len(self.main_data.data_df.columns),
                        align='left',
                        font=dict(color='white', size=13)),
            cells=dict(values=values, fill=dict(color='#F5F8FF'), align='left'), **kwargs)

        fig = go.Figure()
        fig.add_traces([data])
        fig.layout = self.gen_plotly_layout(width=width, height=height, title=title, keep_ui_state=keep_ui_state)

        fig.show()

    def gen_plotly_layout(self,
                          width=None,
                          height=None,
                          title=None,
                          keep_ui_state=True,
                          subplot=False,
                          **layout_params):
        if keep_ui_state:
            uirevision = True
        else:
            uirevision = None

        layout = go.Layout(showlegend=True,
                           plot_bgcolor="#FFF",
                           hovermode="x",
                           hoverdistance=100,  # Distance to show hover label of data point
                           spikedistance=1000,  # Distance to show spike
                           uirevision=uirevision,
                           height=height,
                           width=width,
                           title=title,
                           annotations=to_annotations(self.annotation_df),
                           yaxis=dict(
                               autorange=True,
                               fixedrange=False,
                               zeroline=False,
                               linecolor="#BCCCDC",
                               showgrid=False,
                               # scaleanchor="x", scaleratio=1
                           ),
                           xaxis=dict(
                               linecolor="#BCCCDC",
                               showgrid=False,
                               showspikes=True,  # Show spike line for X-axis
                               # Format spike
                               spikethickness=2,
                               spikedash="dot",
                               spikecolor="#999999",
                               spikemode="across",
                           ),
                           legend_orientation="h",
                           **layout_params)

        if subplot:
            layout.yaxis2 = dict(autorange=True,
                                 fixedrange=False,
                                 zeroline=False)
        return layout


def get_ui_path(name):
    if name is None:
        return os.path.join(zvt_env['ui_path'], '{}.html'.format(now_time_str(fmt=TIME_FORMAT_ISO8601)))
    return os.path.join(zvt_env['ui_path'], f'{name}.html')


def to_annotations(annotation_df: pd.DataFrame):
    """
    annotation_df format:
                                    value    flag    color
    entity_id    timestamp


    :param annotation_df:
    :type annotation_df:
    :return:
    :rtype:
    """
    annotations = []

    if pd_is_not_null(annotation_df):
        for trace_name, df in annotation_df.groupby(level=0):
            if pd_is_not_null(df):
                for (_, timestamp), item in df.iterrows():
                    if 'color' in item:
                        color = item['color']
                    else:
                        color = '#ec0000'

                    value = round(item['value'], 2)
                    annotations.append(dict(
                        x=timestamp,
                        y=value,
                        xref='x',
                        yref='y',
                        text=item['flag'],
                        showarrow=True,
                        align='center',
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=2,
                        # arrowcolor='#030813',
                        ax=-10,
                        ay=-30,
                        bordercolor='#c7c7c7',
                        borderwidth=1,
                        bgcolor=color,
                        opacity=0.8
                    ))

    return annotations


if __name__ == '__main__':
    from zvt.factors.technical.domain import Stock1dMaStateStats
    from zvt.contract.reader import DataReader
    from zvt.domain import Stock
    from zvt.domain.quotes.stock import Stock1dKdata

    data_reader1 = DataReader(codes=['002223'], data_schema=Stock1dKdata, entity_schema=Stock)
    data_reader2 = DataReader(codes=['002223'], data_schema=Stock1dMaStateStats, entity_schema=Stock,
                              columns=['ma5', 'ma10', 'current_count', 'current_pct'])

    data_reader2.data_df['slope'] = 100 * data_reader2.data_df['current_pct'] / data_reader2.data_df['current_count']

    drawer = Drawer(main_df=data_reader1.data_df, factor_df_list=[data_reader2.data_df[['ma5', 'ma10']]],
                    sub_df=data_reader2.data_df[['slope']])
    drawer.draw_kline()
