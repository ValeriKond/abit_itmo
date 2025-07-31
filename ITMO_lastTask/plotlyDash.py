import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, callback_context
import random

# Глобальные переменные для хранения данных
df_sampled = pd.DataFrame()
df2_global = pd.DataFrame()
pq_file_global = None


# Функция для безопасного извлечения данных из столбца 'last_hour_activity'
def safe_extract(x):
    if isinstance(x, dict):
        return x
    else:
        return {'num_transactions': np.nan, 'total_amount': np.nan,
                'unique_merchants': np.nan, 'unique_countries': np.nan,
                'max_single_amount': np.nan}


# Функция для предобработки данных
def preprocess_data(df):
    if df.empty:
        return df, pd.DataFrame()

    # Преобразование 'timestamp' в datetime и округление до секунды
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.floor('s')

    # Нормализация данных из 'last_hour_activity'
    df_last_hour = df['last_hour_activity'].apply(safe_extract)
    df_last_hour_df = pd.json_normalize(df_last_hour)
    df = pd.concat([df.reset_index(drop=True), df_last_hour_df.reset_index(drop=True)], axis=1)

    # Извлечение даты
    df['date'] = df['timestamp'].dt.date

    # Загрузка исторических курсов валют
    df2 = pd.read_parquet('historical_currency_exchange.parquet')

    # Объединение данных транзакций с курсами валют
    df = df.merge(df2.reset_index(), how='left', left_on='date', right_on='date')

    # Функция для конвертации суммы в USD
    def convert_to_usd(row):
        curr = row['currency']
        if curr in df2.columns:
            rate = row[curr]
            if pd.isna(rate) or rate == 0:
                return np.nan
            return row['amount'] / rate
        else:
            return np.nan

    df['amount_usd'] = df.apply(convert_to_usd, axis=1)

    # Извлечение часа и дня недели
    df['hour'] = df['timestamp'].dt.hour
    df['weekday'] = df['timestamp'].dt.day_name()

    return df, df2

# Попытка загрузки выборочных данных для ускорения работы
try:
    pq_file_global = pq.ParquetFile('transaction_fraud_data.parquet')
    num_row_groups = pq_file_global.num_row_groups
    k = min(3, num_row_groups) # Загружаем минимум из 3 или всех доступных групп строк
    selected_groups = random.sample(range(num_row_groups), k)
    print(f"Читаем row groups для выборки: {selected_groups}")
    dfs_sample = [pq_file_global.read_row_group(rg).to_pandas() for rg in selected_groups]
    df_sampled, df2_global = preprocess_data(pd.concat(dfs_sample, ignore_index=True))
    print(f"Размер выборки df_sampled: {df_sampled.shape}")
except Exception as e:
    print(f"Ошибка при загрузке выборочных данных: {e}")
    df_sampled = pd.DataFrame()
    df2_global = pd.DataFrame()

# Подготовка опций для фильтров
vendor_categories = sorted(df_sampled['vendor_category'].dropna().unique()) if not df_sampled.empty else []
channels = sorted(df_sampled['channel'].dropna().unique()) if not df_sampled.empty else []
countries = sorted(df_sampled['country'].dropna().unique()) if not df_sampled.empty else []
cities = sorted(df_sampled['city'].dropna().unique()) if not df_sampled.empty else [] # Добавлен список городов
is_weekend_options = [{'label': 'Будний день', 'value': False},
                      {'label': 'Выходной', 'value': True}]
is_fraud_options = [{'label': 'Легитимные', 'value': False},
                    {'label': 'Мошеннические', 'value': True}]
currency_options = [{'label': col, 'value': col} for col in df2_global.columns if
                    col != 'date'] if not df2_global.empty else []
if {'label': 'USD', 'value': 'USD'} not in currency_options:
    currency_options.insert(0, {'label': 'USD', 'value': 'USD'})

app = Dash(__name__)

# Общие настройки макета для графиков
COMMON_GRAPH_LAYOUT = {
    'plot_bgcolor': '#f8f9fa',
    'paper_bgcolor': '#f8f9fa',
    'font': {'family': 'Arial, sans-serif', 'color': '#343a40'},
    'title_x': 0.5,
    'margin': {'l': 40, 'r': 40, 't': 60, 'b': 40},
    'hovermode': 'closest',
    'transition': {'duration': 500, 'easing': 'cubic-in-out'}
}

# Цветовая палитра
COLORS = {
    'background_start': '#e0f2f7',
    'background_end': '#e8f5e9',
    'text': '#34495e',
    'primary': '#3498db',
    'secondary': '#95a5a6',
    'fraud': '#e74c3c',
    'legit': '#2ecc71',
    'accent': '#f39c12',
    'info_button': '#1abc9c'
}

# Стиль для блоков гипотез
HYPOTHESIS_BLOCK_STYLE = {
    'backgroundColor': '#ffffff',
    'borderRadius': '15px',
    'boxShadow': '0 8px 16px rgba(0,0,0,0.2)',
    'padding': '25px',
    'marginBottom': '25px',
    'border': '1px solid #cceeff',
    'background': 'linear-gradient(145deg, #e0f7fa, #bbdefb)',
    'color': COLORS['text'],
    'position': 'relative',
    'overflow': 'hidden',
}

# Функция для создания контейнера графика с кнопкой информации
def create_graph_container(graph_id, graph_title, info_text):
    return html.Div(style={
        'position': 'relative',
        'marginBottom': '25px',
        'backgroundColor': '#ffffff',
        'borderRadius': '12px',
        'boxShadow': '0 6px 12px rgba(0,0,0,0.15)',
        'padding': '20px',
        'transition': 'transform 0.3s ease-in-out',
    }, children=[
        dcc.Graph(id=graph_id),
        html.Button('i', id=f'info-{graph_id}-button', n_clicks=0, style={
            'position': 'absolute',
            'top': '20px',
            'right': '20px',
            'borderRadius': '50%',
            'width': '35px',
            'height': '35px',
            'border': 'none',
            'backgroundColor': COLORS['info_button'],
            'color': 'white',
            'cursor': 'pointer',
            'fontSize': '18px',
            'fontWeight': 'bold',
            'display': 'flex',
            'justifyContent': 'center',
            'alignItems': 'center',
            'boxShadow': '0 2px 5px rgba(0,0,0,0.2)',
            'transition': 'background-color 0.3s ease, transform 0.2s ease',
        }),
        html.Div(id=f'info-{graph_id}-content', style={
            'display': 'none',
            'padding': '15px',
            'marginTop': '10px',
            'backgroundColor': '#ecf0f1',
            'borderRadius': '8px',
            'border': f'1px solid {COLORS["secondary"]}',
            'position': 'absolute',
            'top': '60px',
            'right': '20px',
            'width': '380px',
            'zIndex': '1000',
            'boxShadow': '0 4px 10px rgba(0,0,0,0.2)',
            'fontSize': '14px',
            'lineHeight': '1.6',
        }, children=info_text)
    ], className='graph-card')


# Макет приложения Dash
app.layout = html.Div(style={
    'fontFamily': 'Roboto, sans-serif',
    'background': f'linear-gradient(135deg, {COLORS["background_start"]}, {COLORS["background_end"]})',
    'color': COLORS['text'],
    'padding': '30px',
    'minHeight': '100vh',
    'boxSizing': 'border-box'
}, children=[
    dcc.Loading( # Индикатор загрузки для всего приложения
        id="loading-full-data",
        type="default",
        children=[
            html.H1('Исследователь данных по обнаружению мошенничества', style={
                'textAlign': 'center',
                'color': COLORS['primary'],
                'marginBottom': '40px',
                'textShadow': '2px 2px 4px rgba(0,0,0,0.15)',
                'fontSize': '2.8em',
                'fontWeight': 'bold'
            }),

            html.Div(style={
                'backgroundColor': '#ffffff',
                'padding': '20px',
                'borderRadius': '15px',
                'boxShadow': '0 6px 12px rgba(0,0,0,0.1)',
                'marginBottom': '30px',
                'textAlign': 'center'
            }, children=[
                html.P(
                    f'Для ускорения работы дашборда, изначально загружена случайная выборка из 3 групп строк ({df_sampled.shape[0] if not df_sampled.empty else 0} транзакций) из общего набора данных. '
                    'Вы можете загрузить всю выборку данных для более полного анализа.',
                    style={'marginBottom': '15px'}),
                html.Button('Загрузить всю выборку данных', id='load-full-data-button', n_clicks=0,
                            style={
                                'backgroundColor': COLORS['primary'],
                                'color': 'white',
                                'border': 'none',
                                'padding': '12px 25px',
                                'borderRadius': '8px',
                                'cursor': 'pointer',
                                'fontSize': '1.1em',
                                'fontWeight': 'bold',
                                'boxShadow': '0 4px 8px rgba(0,0,0,0.2)',
                                'transition': 'background-color 0.3s ease, transform 0.2s ease',
                            })
            ]),

            # Виджеты с ключевыми показателями
            html.Div(style={
                'marginBottom': '40px',
                'padding': '30px',
                'backgroundColor': '#ffffff',
                'borderRadius': '15px',
                'boxShadow': '0 8px 16px rgba(0,0,0,0.2)',
                'display': 'flex',
                'flexWrap': 'wrap',
                'justifyContent': 'space-around',
                'gap': '20px'
            }, children=[
                html.Div([
                    html.H3('Общее количество транзакций',
                            style={'textAlign': 'center', 'color': COLORS['primary'], 'fontSize': '1.2em'}),
                    html.Div(id='widget-total-transactions',
                             style={'fontSize': '2.5em', 'fontWeight': 'bold', 'textAlign': 'center',
                                    'color': COLORS['text']})
                ], style={'flex': '1 1 22%', 'minWidth': '200px', 'backgroundColor': '#f0f8ff', 'padding': '15px',
                          'borderRadius': '10px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.1)'}),

                html.Div([
                    html.H3('Общая сумма мошенничества',
                            style={'textAlign': 'center', 'color': COLORS['fraud'], 'fontSize': '1.2em'}),
                    html.Div(id='widget-total-fraud-amount',
                             style={'fontSize': '2.5em', 'fontWeight': 'bold', 'textAlign': 'center',
                                    'color': COLORS['fraud']})
                ], style={'flex': '1 1 22%', 'minWidth': '200px', 'backgroundColor': '#fff0f0', 'padding': '15px',
                          'borderRadius': '10px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.1)'}),

                html.Div([
                    html.H3('Процент мошенничества',
                            style={'textAlign': 'center', 'color': COLORS['fraud'], 'fontSize': '1.2em'}),
                    html.Div(id='widget-fraud-percentage',
                             style={'fontSize': '2.5em', 'fontWeight': 'bold', 'textAlign': 'center',
                                    'color': COLORS['fraud']})
                ], style={'flex': '1 1 22%', 'minWidth': '200px', 'backgroundColor': '#fff0f0', 'padding': '15px',
                          'borderRadius': '10px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.1)'}),

                html.Div([
                    html.H3('Средняя сумма транзакции',
                            style={'textAlign': 'center', 'color': COLORS['accent'], 'fontSize': '1.2em'}),
                    html.Div(id='widget-avg-transaction-amount',
                             style={'fontSize': '2.5em', 'fontWeight': 'bold', 'textAlign': 'center',
                                    'color': COLORS['text']})
                ], style={'flex': '1 1 22%', 'minWidth': '200px', 'backgroundColor': '#fffae0', 'padding': '15px',
                          'borderRadius': '10px', 'boxShadow': '0 2px 5px rgba(0,0,0,0.1)'}),
            ]),

            # Блоки описания задачи и гипотез
            html.Div(style={
                'backgroundColor': '#ffffff',
                'padding': '30px',
                'borderRadius': '15px',
                'boxShadow': '0 8px 16px rgba(0,0,0,0.2)',
                'marginBottom': '40px'
            }, children=[
                html.H2('Описание задачи и гипотезы',
                       style={'textAlign': 'center', 'color': COLORS['secondary'], 'marginBottom': '25px',
                               'fontSize': '2em'}),

                html.Div(style=HYPOTHESIS_BLOCK_STYLE, children=[
                    html.H3('Исходная задача:',
                            style={'marginTop': '0', 'color': COLORS['primary'], 'fontSize': '1.5em'}),
                    html.P(
                        'Анализируем финансовые транзакции, чтобы помочь компании. Цель — не только выявить мошенничество, но и найти способы улучшить работу. Для этого создан интерактивный дашборд и гипотезы.'),
                ]),

                html.Div(style=HYPOTHESIS_BLOCK_STYLE, children=[
                    html.H3('Продуктовые гипотезы',
                            style={'color': COLORS['primary'], 'fontSize': '1.5em'}),
                    html.Ul(style={'listStyleType': 'none', 'paddingLeft': '0'},
                            children=[
                                html.Li([html.B('Улучшение клиентского опыта:'),
                                         ' Если транзакции через определенные устройства или каналы ', html.B('реже'),
                                         ' связаны с мошенничеством, их можно обрабатывать ', html.B('быстрее.'),
                                         ' Это уменьшит задержки и ложные блокировки для обычных клиентов, повышая качество обслуживания. (См. графики: ',
                                         html.A('Доля мошенничества по устройствам', href='#fraud_by_device',
                                                style={'color': COLORS['primary']}), ', ',
                                         html.A('Общее распределение транзакций', href='#fraud_overview',
                                                style={'color': COLORS['primary']}), ')']),
                                html.Li([html.B('Более точное выявление мошенничества:'),
                                         ' Используя данные о транзакциях за границей, рискованных продавцах и активности клиента за последний час, можно создать правила для обнаружения мошенничества. Поможет ловить больше реальных мошенников и снижать фин. потери. (См. графики: ',
                                         html.A('Корреляция активности за последний час с мошенничеством',
                                                href='#last_hour_activity_correlation',
                                                style={'color': COLORS['primary']}), ', ',
                                         html.A('Средняя сумма транзакций (USD) по странам',
                                                href='#amount_usd_by_country',
                                                style={'color': COLORS['primary']}), ')']),
                                html.Li([html.B('Индивидуальный подход к клиентам:'),
                                         ' Зная обычные траты клиента и его недавнюю активность, можно настроить систему обнаружения мошенничества индивидуально. Это сделает систему более гибкой и точной, адаптируясь к поведению каждого клиента. (См. графики: ',
                                         html.A('Распределение сумм транзакций (USD)', href='#transaction_amounts',
                                                style={'color': COLORS['primary']}), ', ',
                                         html.A('Количество транзакций по датам', href='#transactions_counts',
                                                style={'color': COLORS['primary']}), ')']),
                                html.Li([html.B('Эффективное распределение ресурсов:'),
                                         ' Выявление пиковых часов/дней для мошенничества и наиболее рискованных стран/валют поможет разумно распределять силы команды по борьбе с мошенничеством, экономя время и деньги. (См. графики: ',
                                         html.A('Доля мошенничества по часам суток', href='#fraud_by_hour',
                                                style={'color': COLORS['primary']}), ', ',
                                         html.A('Доля мошенничества: выходные vs будни', href='#fraud_vs_weekend',
                                                style={'color': COLORS['primary']}), ', ',
                                         html.A('Частота использования валют', href='#currency_usage',
                                                style={'color': COLORS['primary']}),
                                         ')']),
                            ]),
                ]),

                html.Div(style=HYPOTHESIS_BLOCK_STYLE, children=[
                    html.H3('Технические гипотезы',
                            style={'color': COLORS['primary'], 'fontSize': '1.5em'}),
                    html.Ul(style={'listStyleType': 'none', 'paddingLeft': '0'},
                            children=[
                                html.Li([html.B('Активность за последний час:'),
                                         ' Показатели активности клиента за последний час (количество транзакций, общая сумма, уникальные продавцы/страны, максимальная сумма) должны быть сильно связаны с мошенничеством. Резкий всплеск активности может указывать на подозрительные операции. (См. график: ',
                                         html.A('Корреляция активности за последний час с мошенничеством',
                                                href='#last_hour_activity_correlation',
                                                style={'color': COLORS['primary']}), ')']),
                                html.Li([html.B('География и валюта:'),
                                         ' Транзакции вне домашней страны или в определенных странах/валютах, вероятно, будут иметь более высокий риск мошенничества. (См. графики: ',
                                         html.A('Средняя сумма транзакций (USD) по странам',
                                                href='#amount_usd_by_country',
                                                style={'color': COLORS['primary']}), ', ',
                                         html.A('Частота использования валют', href='#currency_usage',
                                                style={'color': COLORS['primary']}),
                                         ')']),
                                html.Li([html.B('Устройство и канал:'),
                                         ' Определенные устройства (например, устаревшие браузеры) и каналы (например, оплата без физического присутствия карты) могут быть чаще связаны с мошенничеством. (См. график: ',
                                         html.A('Доля мошенничества по устройствам', href='#fraud_by_device',
                                                style={'color': COLORS['primary']}), ')']),
                                html.Li([html.B('Время транзакции:'),
                                         ' Мошенничество может иметь четкие временные паттерны (часы, выходные). Например, оно может быть чаще в нерабочее время или в выходные дни. (См. графики: ',
                                         html.A('Доля мошенничества по часам суток', href='#fraud_by_hour',
                                                style={'color': COLORS['primary']}), ', ',
                                         html.A('Доля мошенничества: выходные vs будни', href='#fraud_vs_weekend',
                                                style={'color': COLORS['primary']}), ')']),
                                html.Li([html.B('Сумма транзакции:'),
                                         ' Суммы мошеннических транзакций могут отличаться от обычных: очень мелкие (для проверки карт) или очень крупные (для максимальной выгоды). (См. график: ',
                                         html.A('Распределение сумм транзакций (USD)', href='#transaction_amounts',
                                                style={'color': COLORS['primary']}), ')']),
                            ])
                ]),
            ]),

            # Блок фильтров
            html.Div(style={
                'marginBottom': '40px',
                'padding': '30px',
                'backgroundColor': '#ffffff',
                'borderRadius': '15px',
                'boxShadow': '0 8px 16px rgba(0,0,0,0.2)',
                'display': 'flex',
                'flexWrap': 'wrap',
                'justifyContent': 'space-between',
                'gap': '20px'
            }, children=[
                html.Div([
                    html.Label('Фильтр по категории вендора:',
                               style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='vendor_category_filter',
                        options=[{'label': v, 'value': v} for v in vendor_categories],
                        multi=True,
                        placeholder='Выберите категории...',
                        style={'borderRadius': '8px', 'borderColor': '#ced4da',
                               'boxShadow': '0 2px 4px rgba(0,0,0,0.05)'}
                    ),
                ], style={'flex': '1 1 30%'}),

                html.Div([
                    html.Label('Фильтр по каналу:',
                               style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='channel_filter',
                        options=[{'label': c, 'value': c} for c in channels],
                        multi=True,
                        placeholder='Выберите каналы...',
                        style={'borderRadius': '8px', 'borderColor': '#ced4da',
                               'boxShadow': '0 2px 4px rgba(0,0,0,0.05)'}
                    ),
                ], style={'flex': '1 1 30%'}),

                html.Div([
                    html.Label('Фильтр по стране:',
                               style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='country_filter',
                        options=[{'label': c, 'value': c} for c in countries],
                        multi=True,
                        placeholder='Выберите страны...',
                        style={'borderRadius': '8px', 'borderColor': '#ced4da',
                               'boxShadow': '0 2px 4px rgba(0,0,0,0.05)'}
                    ),
                ], style={'flex': '1 1 30%'}),

                html.Div([ # Новый фильтр по городу
                    html.Label('Фильтр по городу:',
                               style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='city_filter',
                        options=[{'label': c, 'value': c} for c in cities],
                        multi=True,
                        placeholder='Выберите города...',
                        style={'borderRadius': '8px', 'borderColor': '#ced4da',
                               'boxShadow': '0 2px 4px rgba(0,0,0,0.05)'}
                    ),
                ], style={'flex': '1 1 30%'}),

                html.Div([
                    html.Label('Фильтр по дню недели:',
                               style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='is_weekend_filter',
                        options=is_weekend_options,
                        multi=True,
                        placeholder='Будний день / Выходной...',
                        style={'borderRadius': '8px', 'borderColor': '#ced4da',
                               'boxShadow': '0 2px 4px rgba(0,0,0,0.05)'}
                    ),
                ], style={'flex': '1 1 30%'}),

                html.Div([
                    html.Label('Фильтр по типу транзакции:',
                               style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='is_fraud_filter',
                        options=is_fraud_options,
                        multi=True,
                        placeholder='Легитимные / Мошеннические...',
                        style={'borderRadius': '8px', 'borderColor': '#ced4da',
                               'boxShadow': '0 2px 4px rgba(0,0,0,0.05)'}
                    ),
                ], style={'flex': '1 1 30%'}),
                html.Div([
                    html.Label('Целевая валюта для отображения:',
                               style={'fontWeight': 'bold', 'marginBottom': '10px', 'display': 'block'}),
                    dcc.Dropdown(
                        id='target-currency-filter',
                        options=currency_options,
                        value='USD',
                        clearable=False,
                        style={'borderRadius': '8px', 'borderColor': '#ced4da',
                               'boxShadow': '0 2px 4px rgba(0,0,0,0.05)'}
                    ),
                ], style={'flex': '1 1 30%'}),
            ]),

            # Обзорный график распределения транзакций
            create_graph_container('fraud_overview', 'Общее распределение транзакций',
                                   'Этот круговой график показывает общую долю мошеннических и легитимных транзакций в выбранной выборке данных. Он дает быстрое представление о распространенности мошенничества.'),

            # Вкладки для различных аналитических разделов
            dcc.Tabs(id='main-tabs', value='tab-1', style={
                'fontFamily': 'Roboto, sans-serif',
                'backgroundColor': '#ffffff',
                'borderRadius': '15px',
                'boxShadow': '0 8px 16px rgba(0,0,0,0.2)',
                'padding': '15px'
            }, children=[
                dcc.Tab(label='Анализ мошенничества', value='tab-1', style={'padding': '18px', 'fontSize': '1.1em'},
                        selected_style={'fontWeight': 'bold', 'borderTop': f'4px solid {COLORS["primary"]}',
                                        'padding': '18px',
                                        'color': COLORS['primary']}, children=[
                        html.Div(style={'padding': '25px'}, children=[
                            create_graph_container('fraud_ratio_by_category',
                                                   'Доля мошенничества по категориям вендоров',
                                                   'Этот столбчатый график показывает процент мошеннических транзакций для каждой категории продавцов. Он помогает выявить, в каких сферах мошенничество встречается чаще всего.'),
                            create_graph_container('fraud_vs_weekend', 'Доля мошенничества: выходные vs будни',
                                                   'Этот график сравнивает среднюю долю мошеннических транзакций в выходные и будние дни, помогая понять, влияет ли день недели на риск мошенничества.'),
                            create_graph_container('fraud_by_hour', 'Доля мошенничества по часам суток',
                                                   'Этот линейный график отображает, как меняется доля мошенничества в течение суток (по часам). Это может выявить пиковые часы для мошеннической активности.'),
                            create_graph_container('fraud_by_device', 'Доля мошенничества по устройствам (ТОП 20)',
                                                   'Этот график показывает процент мошеннических транзакций по типу устройства, с которого они были совершены. Все, что с картами - fraud (data mistake???)'),
                            create_graph_container('fraud_by_vendor_type', 'Доля мошенничества по типу вендора',
                                                   'Этот график показывает процент мошеннических транзакций по типу вендора (например, "онлайн", "офлайн").'),
                            create_graph_container('fraud_by_card_type', 'Доля мошенничества по типу карты',
                                                   'Этот график показывает процент мошеннических транзакций по типу используемой карты (например, Basic Credit, Gold Credit).'),
                            create_graph_container('fraud_by_card_present',
                                                   'Доля мошенничества: карта присутствует / отсутствует',
                                                   'Этот график сравнивает долю мошенничества в транзакциях, где карта физически присутствовала (POS), и где ее не было. ВСЕ тарнзакции с картой помечены как fraud (mistake??)'),
                            create_graph_container('fraud_outside_home_country',
                                                   'Доля мошенничества: внутри / вне домашней страны',
                                                   'Этот график показывает долю мошенничества для транзакций, совершенных внутри и вне домашней страны клиента.'),
                            create_graph_container('fraud_high_risk_vendor',
                                                   'Доля мошенничества: рискованный / нерискованный вендор',
                                                   'Этот график сравнивает долю мошенничества для транзакций, совершенных у рискованных и нерискованных вендоров.'),
                            create_graph_container('fraud_by_city_size', 'Доля мошенничества по размеру города',
                                                   'Этот график показывает долю мошенничества в зависимости от размера города, где была совершена транзакция.'),
                        ])
                    ]),
                dcc.Tab(label='Транзакционная активность', value='tab-2',
                        style={'padding': '18px', 'fontSize': '1.1em'},
                        selected_style={'fontWeight': 'bold', 'borderTop': f'4px solid {COLORS["primary"]}',
                                        'padding': '18px',
                                        'color': COLORS['primary']}, children=[
                        html.Div(style={'padding': '25px'}, children=[
                            create_graph_container('transaction_amounts', 'Распределение сумм транзакций (USD)',
                                                   'Гистограмма, показывающая, как распределяются суммы транзакций (в USD). Ось Y логарифмическая, чтобы лучше видеть распределение как мелких, так и крупных сумм.'),
                            create_graph_container('transactions_counts', 'Количество транзакций по датам',
                                                   'Этот линейный график отображает общее количество транзакций по дням, позволяя увидеть динамику активности во времени.'),
                            create_graph_container('last_hour_activity_correlation',
                                                   'Корреляция активности за последний час с мошенничеством',
                                                   'Этот столбчатый график показывает, насколько сильно различные показатели активности клиента за последний час (например, количество транзакций, общая сумма) связаны с вероятностью мошенничества. Чем выше столбец, тем сильнее связь.'),
                        ])
                    ]),
                dcc.Tab(label='Валюты и география', value='tab-3', style={'padding': '18px', 'fontSize': '1.1em'},
                        selected_style={'fontWeight': 'bold', 'borderTop': f'4px solid {COLORS["primary"]}',
                                        'padding': '18px',
                                        'color': COLORS['primary']}, children=[
                        html.Div(style={'padding': '25px'}, children=[
                            create_graph_container('amount_usd_by_country',
                                                   'Средняя сумма транзакций (USD) по странам',
                                                   'Этот график показывает среднюю сумму транзакций в долларах США для стран. Помогает выявить страны с типично более крупными или мелкими операциями.'),
                            create_graph_container('currency_usage', 'Частота использования валют',
                                                   'Этот график показывает, как часто используются различные валюты в транзакциях, давая представление о географическом распределении операций.'),
                            create_graph_container('top_fraudulent_vendors',
                                                   'Топ 20 вендоров по количеству мошеннических транзакций',
                                                   'Этот график показывает 20 вендоров, у которых было наибольшее количество мошеннических транзакций.'),
                            create_graph_container('top_fraudulent_cities',
                                                   'Топ 20 городов по количеству мошеннических транзакций',
                                                   'Этот график показывает 20 городов, в которых было зарегистрировано наибольшее количество мошеннических транзакций.'),
                        ])
                    ]),
                dcc.Tab(label='Мошеннические клиенты', value='tab-4', style={'padding': '18px', 'fontSize': '1.1em'},
                        selected_style={'fontWeight': 'bold', 'borderTop': f'4px solid {COLORS["primary"]}',
                                        'padding': '18px',
                                        'color': COLORS['primary']}, children=[
                        html.Div(style={'padding': '25px'}, children=[
                            create_graph_container('top_fraudulent_customers', 'Топ 10 клиентов по сумме мошенничества',
                                                   'Эта таблица отображает 10 клиентов, которые совершили наибольшую сумму мошеннических транзакций.'),
                        ])
                    ]),
            ]),
            dcc.Store(id='full-data-store', data=None),
            dcc.Store(id='exchange-rates-store', data=df2_global.to_json(date_format='iso', orient='split'))
        ]
    )
])


# Функция для создания колбэков для кнопок информации
def get_toggle_callback(graph_id):
    @app.callback(
        Output(f'info-{graph_id}-content', 'style'),
        Input(f'info-{graph_id}-button', 'n_clicks'),
        State(f'info-{graph_id}-content', 'style')
    )
    def toggle_info(n_clicks, current_style):
        if not n_clicks:
            return {'display': 'none', **current_style}

        if current_style and current_style.get('display') == 'block':
            current_style['display'] = 'none'
        else:
            current_style['display'] = 'block'
        return current_style

    return toggle_info

# Применение колбэков для всех информационных кнопок
get_toggle_callback('fraud_overview')
get_toggle_callback('fraud_ratio_by_category')
get_toggle_callback('fraud_vs_weekend')
get_toggle_callback('fraud_by_hour')
get_toggle_callback('fraud_by_device')
get_toggle_callback('transaction_amounts')
get_toggle_callback('transactions_counts')
get_toggle_callback('last_hour_activity_correlation')
get_toggle_callback('amount_usd_by_country')
get_toggle_callback('currency_usage')
get_toggle_callback('fraud_by_vendor_type')
get_toggle_callback('fraud_by_card_type')
get_toggle_callback('fraud_by_card_present')
get_toggle_callback('fraud_outside_home_country')
get_toggle_callback('fraud_high_risk_vendor')
get_toggle_callback('fraud_by_city_size')
get_toggle_callback('top_fraudulent_vendors')
get_toggle_callback('top_fraudulent_cities')
get_toggle_callback('top_fraudulent_customers')


# Колбэк для загрузки полной выборки данных
@app.callback(
    [Output('full-data-store', 'data'),
     Output('exchange-rates-store', 'data', allow_duplicate=True)],
    Input('load-full-data-button', 'n_clicks'),
    prevent_initial_call=True
)
def load_full_data_to_store(n_clicks):
    if n_clicks > 0:
        print(
            "Загружаем полную выборку данных и курсы валют в хранилище...")
        try:
            df_full, df2_full = preprocess_data(pq_file_global.read().to_pandas())
            print(
                f"Размер полной выборки загруженной в хранилище: {df_full.shape}")
            return df_full.to_json(date_format='iso', orient='split'), df2_full.to_json(date_format='iso',
                                                                                        orient='split')
        except Exception as e:
            print(f"Ошибка при загрузке полной выборки данных: {e}")
            return None, None
    return None, df2_global.to_json(date_format='iso', orient='split')


# Функция для фильтрации данных
def filter_data(df, df2, vendor_cats, channels, countries, cities, is_weekend_val, is_fraud_val, target_currency):
    dff = df.copy()
    if vendor_cats and len(vendor_cats) > 0:
        dff = dff[dff['vendor_category'].isin(vendor_cats)]
    if channels and len(channels) > 0:
        dff = dff[dff['channel'].isin(channels)]
    if countries and len(countries) > 0:
        dff = dff[dff['country'].isin(countries)]
    if cities and len(cities) > 0: # Применение фильтра по городу
        dff = dff[dff['city'].isin(cities)]
    if is_weekend_val is not None and len(is_weekend_val) > 0:
        dff = dff[dff['is_weekend'].isin(is_weekend_val)]
    if is_fraud_val is not None and len(is_fraud_val) > 0:
        dff = dff[dff['is_fraud'].isin(is_fraud_val)]

    # Конвертация валюты, если целевая валюта не USD
    if target_currency and target_currency != 'USD' and not df2.empty:
        dff['date'] = pd.to_datetime(dff['date'])
        df2['date'] = pd.to_datetime(df2['date'])

        temp_df = dff.merge(df2[['date', target_currency]], on='date', how='left', suffixes=('', '_target_rate'))

        temp_df['amount_converted'] = temp_df.apply(
            lambda row: row['amount_usd'] * row[f'{target_currency}_target_rate']
            if pd.notna(row[f'{target_currency}_target_rate']) else np.nan, axis=1
        )
        dff = temp_df
    else:
        dff['amount_converted'] = dff['amount_usd']

    return dff


# Главный колбэк для обновления всех графиков и виджетов
@app.callback(
    [Output('fraud_overview', 'figure'),
     Output('fraud_ratio_by_category', 'figure'),
     Output('fraud_vs_weekend', 'figure'),
     Output('fraud_by_hour', 'figure'),
     Output('fraud_by_device', 'figure'),
     Output('transaction_amounts', 'figure'),
     Output('transactions_counts', 'figure'),
     Output('last_hour_activity_correlation', 'figure'),
     Output('amount_usd_by_country', 'figure'),
     Output('currency_usage', 'figure'),
     Output('widget-total-transactions', 'children'),
     Output('widget-total-fraud-amount', 'children'),
     Output('widget-fraud-percentage', 'children'),
     Output('widget-avg-transaction-amount', 'children'),
     Output('fraud_by_vendor_type', 'figure'),
     Output('fraud_by_card_type', 'figure'),
     Output('fraud_by_card_present', 'figure'),
     Output('fraud_outside_home_country', 'figure'),
     Output('fraud_high_risk_vendor', 'figure'),
     Output('fraud_by_city_size', 'figure'),
     Output('top_fraudulent_vendors', 'figure'),
     Output('top_fraudulent_cities', 'figure'),
     Output('top_fraudulent_customers', 'figure'),
     ],
    [Input('vendor_category_filter', 'value'),
     Input('channel_filter', 'value'),
     Input('country_filter', 'value'),
     Input('city_filter', 'value'), # Добавлен входной параметр для фильтра по городу
     Input('is_weekend_filter', 'value'),
     Input('is_fraud_filter', 'value'),
     Input('target-currency-filter', 'value'),
     Input('full-data-store', 'data'),
     Input('exchange-rates-store', 'data')]
)
def update_graphs(vendor_cats, channels, countries, cities, is_weekend_val, is_fraud_val, target_currency, full_data_json,
                  exchange_rates_json):
    # Определение текущего DataFrame (выборка или полные данные)
    if full_data_json is not None:
        current_df = pd.read_json(full_data_json, orient='split')
    else:
        current_df = df_sampled

    # Определение DataFrame с курсами валют
    if exchange_rates_json is not None:
        df2 = pd.read_json(exchange_rates_json, orient='split')
    else:
        df2 = pd.DataFrame()

    # Фильтрация данных
    dff = filter_data(current_df, df2, vendor_cats, channels, countries, cities, is_weekend_val, is_fraud_val, target_currency)

    # Расчет показателей для виджетов
    total_transactions = len(dff)
    total_fraud_amount = dff[dff['is_fraud'] == True]['amount_converted'].sum() if 'is_fraud' in dff.columns else 0
    fraud_percentage = dff['is_fraud'].mean() * 100 if len(dff) > 0 and 'is_fraud' in dff.columns else 0
    avg_transaction_amount = dff['amount_converted'].mean() if len(dff) > 0 else 0

    widget_total_transactions_val = f"{total_transactions:,}".replace(",", " ")
    widget_total_fraud_amount_val = f"{total_fraud_amount:,.2f} {target_currency}".replace(",", " ")
    widget_fraud_percentage_val = f"{fraud_percentage:.2f}%"
    widget_avg_transaction_amount_val = f"{avg_transaction_amount:,.2f} {target_currency}".replace(",", " ")


    # Возвращение пустых графиков, если данных нет
    if dff.empty:
        empty_fig = go.Figure()
        empty_fig.update_layout(
            title="Нет данных для отображения с выбранными фильтрами",
            xaxis={'visible': False},
            yaxis={'visible': False},
            annotations=[
                {
                    'text': 'Пожалуйста, измените фильтры.',
                    'xref': 'paper',
                    'yref': 'paper',
                    'showarrow': False,
                    'font': {'size': 20, 'color': COLORS['secondary']}
                }
            ],
            **COMMON_GRAPH_LAYOUT
        )
        # Возвращаем 19 пустых фигур и значения виджетов
        return (empty_fig,) * 19 + (
        widget_total_transactions_val, widget_total_fraud_amount_val, widget_fraud_percentage_val,
        widget_avg_transaction_amount_val)

    # Общее распределение транзакций (круговая диаграмма)
    fraud_count = dff['is_fraud'].sum()
    legit_count = len(dff) - fraud_count
    fig_overview = go.Figure(data=[go.Pie(labels=['Легитимные', 'Мошеннические'],
                                          values=[legit_count, fraud_count],
                                          hole=.3,
                                          marker_colors=[COLORS['legit'], COLORS['fraud']],
                                          pull=[0, 0.05] if fraud_count > 0 else [0, 0],
                                          textinfo='percent+label+value',
                                          insidetextorientation='radial'
                                          )])
    fig_overview.update_layout(
        title_text='Общее распределение транзакций',
        **COMMON_GRAPH_LAYOUT
    )

    # Доля мошенничества по категориям вендоров
    fraud_cat = dff.groupby('vendor_category')['is_fraud'].mean().sort_values(ascending=False).reset_index()
    fig_fraud_cat = px.bar(fraud_cat, x='vendor_category', y='is_fraud',
                           labels={'is_fraud': 'Доля мошенничества', 'vendor_category': 'Категория вендора'},
                           title='Доля мошенничества по категориям вендоров',
                           color='is_fraud',
                           color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                           hover_data={'is_fraud': ':.2%'},
                           text_auto='.2%')
    fig_fraud_cat.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_fraud_cat.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества: выходные vs будни
    weekend_fraud = dff.groupby('is_weekend')['is_fraud'].mean().reset_index()
    weekend_fraud['is_weekend_label'] = weekend_fraud['is_weekend'].apply(
        lambda x: 'Выходной' if x else 'Будний день')
    fig_fraud_weekend = px.bar(weekend_fraud, x='is_weekend_label', y='is_fraud',
                               labels={'is_weekend_label': 'День недели', 'is_fraud': 'Доля мошенничества'},
                               title='Доля мошенничества: выходные vs будни',
                               color='is_fraud',
                               color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                               hover_data={'is_fraud': ':.2%'},
                               text_auto='.2%')
    fig_fraud_weekend.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_fraud_weekend.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества по часам суток
    fraud_hour = dff.groupby('hour')['is_fraud'].mean().reset_index()
    fig_fraud_hour = px.line(fraud_hour, x='hour', y='is_fraud',
                             labels={'hour': 'Час суток', 'is_fraud': 'Доля мошенничества'},
                             title='Доля мошенничества по часам суток',
                             line_shape='spline',
                             markers=True,
                             color_discrete_sequence=[COLORS['primary']])
    fig_fraud_hour.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_fraud_hour.update_traces(mode='lines+markers+text',
                                 text=fraud_hour['is_fraud'].apply(lambda x: f'{x:.2%}'),
                                 textposition='top center',
                                 marker=dict(size=8, symbol='circle'))

    # Доля мошенничества по устройствам (ТОП 20)
    device_stats = dff.groupby('device')['is_fraud'].agg(['sum', 'count']).reset_index()
    device_stats['fraud_ratio'] = device_stats['sum'] / device_stats['count']
    min_transactions_for_device_display = 5
    device_stats = device_stats[device_stats['count'] >= min_transactions_for_device_display]
    fraud_device = device_stats.sort_values(by='fraud_ratio', ascending=False).head(20)

    fig_fraud_device = px.bar(fraud_device, x='device', y='fraud_ratio',
                              labels={'fraud_ratio': 'Доля мошенничества', 'device': 'Устройство'},
                              title='Доля мошенничества по устройствам (ТОП 20)',
                              color='fraud_ratio',
                              color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                              hover_data={'count': True, 'sum': True, 'fraud_ratio': ':.2%'},
                              text_auto='.2%')
    fig_fraud_device.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_fraud_device.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Распределение сумм транзакций (USD)
    fig_amounts = px.histogram(dff, x='amount_converted', nbins=100, log_y=True,
                               title=f'Распределение сумм транзакций ({target_currency})',
                               labels={'amount_converted': f'Сумма ({target_currency})'},
                               color_discrete_sequence=[COLORS['accent']],
                               text_auto=True)
    fig_amounts.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_amounts.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Количество транзакций по датам
    dff_time = dff.groupby(dff['timestamp'].dt.date).size().reset_index(name='count')
    dff_time.columns = ['date', 'count']
    fig_tx_counts = px.line(dff_time, x='date', y='count',
                            labels={'date': 'Дата', 'count': 'Количество транзакций'},
                            title='Количество транзакций по датам',
                            line_shape='spline',
                            markers=True,
                            color_discrete_sequence=[COLORS['primary']])
    fig_tx_counts.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_tx_counts.update_traces(mode='lines+markers+text',
                                text=dff_time['count'],
                                textposition='top center',
                                marker=dict(size=8, symbol='circle'))

    # Корреляция активности за последний час с мошенничеством
    df_corr_sample = dff[
        ['num_transactions', 'total_amount', 'unique_merchants', 'unique_countries', 'max_single_amount',
         'is_fraud']].dropna()
    corr_matrix = df_corr_sample.corr()
    if 'is_fraud' in corr_matrix.columns and not corr_matrix['is_fraud'].drop('is_fraud',
                                                                              errors='ignore').empty:
        corr_with_fraud = corr_matrix['is_fraud'].drop('is_fraud',
                                                       errors='ignore')
        fig_corr = go.Figure(data=[go.Bar(x=corr_with_fraud.index, y=corr_with_fraud.values,
                                          marker_color=[COLORS['fraud'] if val > 0 else COLORS['legit'] for val in
                                                        corr_with_fraud.values],
                                          text=corr_with_fraud.values,
                                          texttemplate='%{text:.2f}',
                                          textposition='auto')])
        fig_corr.update_layout(title='Корреляция активности за последний час с мошенничеством',
                               yaxis_title='Корреляция с is_fraud',
                               **COMMON_GRAPH_LAYOUT)
        fig_corr.update_traces(marker_line_color='white', marker_line_width=1.5)
    else:
        fig_corr = go.Figure()
        fig_corr.update_layout(title="Нет данных для расчета корреляции",
                               **COMMON_GRAPH_LAYOUT)

    # Средняя сумма транзакций (USD) по странам
    if not dff['country'].empty:
        top_countries = dff['country'].value_counts().nlargest(20).index
        country_amounts = dff[dff['country'].isin(top_countries)].groupby(['country', 'is_fraud'])[
            'amount_converted'].mean().reset_index()
        fig_amount_usd_by_country = px.bar(country_amounts, x='country', y='amount_converted',
                                    labels={'country': 'Страна',
                                            'amount_converted': f'Средняя сумма ({target_currency})',
                                            'is_fraud': 'Тип операции'},
                                    title=f'Средняя сумма транзакций ({target_currency}) по странам (ТОП 20)',
                                    color='is_fraud',
                                    color_discrete_map={True: COLORS['fraud'], False: COLORS['legit']},
                                    text_auto='.2s')
        fig_amount_usd_by_country.update_layout(**COMMON_GRAPH_LAYOUT)
        fig_amount_usd_by_country.update_traces(marker_line_color='white', marker_line_width=1.5)
    else:
        fig_amount_usd_by_country = go.Figure()
        fig_amount_usd_by_country.update_layout(title="Нет данных по странам для отображения",
                                         **COMMON_GRAPH_LAYOUT)

    # Частота использования валют
    currency_counts = dff.groupby(['currency', 'is_fraud']).size().reset_index(name='count')
    fig_currency_usage = px.bar(currency_counts, x='currency', y='count',
                                title='Частота использования валют',
                                labels={'currency': 'Валюта', 'count': 'Количество транзакций',
                                        'is_fraud': 'Тип операции'},
                                color='is_fraud',
                                color_discrete_map={True: COLORS['fraud'], False: COLORS['legit']},
                                text_auto=True)
    fig_currency_usage.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_currency_usage.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества по типу вендора
    fraud_vendor_type = dff.groupby('vendor_type')['is_fraud'].mean().sort_values(ascending=False).reset_index()
    fig_vendor_type_fraud = px.bar(fraud_vendor_type, x='vendor_type', y='is_fraud',
                                   labels={'is_fraud': 'Доля мошенничества', 'vendor_type': 'Тип вендора'},
                                   title='Доля мошенничества по типу вендора',
                                   color='is_fraud',
                                   color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                                   hover_data={'is_fraud': ':.2%'},
                                   text_auto='.2%')
    fig_vendor_type_fraud.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_vendor_type_fraud.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества по типу карты
    fraud_card_type = dff.groupby('card_type')['is_fraud'].mean().sort_values(ascending=False).reset_index()
    fig_card_type_fraud = px.bar(fraud_card_type, x='card_type', y='is_fraud',
                                 labels={'is_fraud': 'Доля мошенничества', 'card_type': 'Тип карты'},
                                 title='Доля мошенничества по типу карты',
                                 color='is_fraud',
                                 color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                                 hover_data={'is_fraud': ':.2%'},
                                 text_auto='.2%')
    fig_card_type_fraud.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_card_type_fraud.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества: карта присутствует / отсутствует
    fraud_card_present = dff.groupby('is_card_present')['is_fraud'].mean().reset_index()
    fraud_card_present['label'] = fraud_card_present['is_card_present'].apply(
        lambda x: 'Карта присутствует' if x else 'Карта отсутствует')
    fig_card_present_fraud = px.bar(fraud_card_present, x='label', y='is_fraud',
                                    labels={'is_fraud': 'Доля мошенничества', 'label': 'Присутствие карты'},
                                    title='Доля мошенничества: карта присутствует / отсутствует',
                                    color='is_fraud',
                                    color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                                    hover_data={'is_fraud': ':.2%'},
                                    text_auto='.2%')
    fig_card_present_fraud.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_card_present_fraud.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества: внутри / вне домашней страны
    fraud_outside_home = dff.groupby('is_outside_home_country')['is_fraud'].mean().reset_index()
    fraud_outside_home['label'] = fraud_outside_home['is_outside_home_country'].apply(
        lambda x: 'Вне домашней страны' if x else 'Внутри домашней страны')
    fig_outside_home_fraud = px.bar(fraud_outside_home, x='label', y='is_fraud',
                                    labels={'is_fraud': 'Доля мошенничества', 'label': 'География транзакции'},
                                    title='Доля мошенничества: внутри / вне домашней страны',
                                    color='is_fraud',
                                    color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                                    hover_data={'is_fraud': ':.2%'},
                                    text_auto='.2%')
    fig_outside_home_fraud.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_outside_home_fraud.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества: рискованный / нерискованный вендор
    fraud_high_risk_vendor = dff.groupby('is_high_risk_vendor')['is_fraud'].mean().reset_index()
    fraud_high_risk_vendor['label'] = fraud_high_risk_vendor['is_high_risk_vendor'].apply(
        lambda x: 'Рискованный вендор' if x else 'Нерискованный вендор')
    fig_high_risk_vendor_fraud = px.bar(fraud_high_risk_vendor, x='label', y='is_fraud',
                                        labels={'is_fraud': 'Доля мошенничества', 'label': 'Тип вендора по риску'},
                                        title='Доля мошенничества: рискованный / нерискованный вендор',
                                        color='is_fraud',
                                        color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                                        hover_data={'is_fraud': ':.2%'},
                                        text_auto='.2%')
    fig_high_risk_vendor_fraud.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_high_risk_vendor_fraud.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Доля мошенничества по размеру города
    fraud_city_size = dff.groupby('city_size')['is_fraud'].mean().sort_values(ascending=False).reset_index()
    fig_fraud_city_size = px.bar(fraud_city_size, x='city_size', y='is_fraud',
                                 labels={'is_fraud': 'Доля мошенничества', 'city_size': 'Размер города'},
                                 title='Доля мошенничества по размеру города',
                                 color='is_fraud',
                                 color_continuous_scale=[COLORS['legit'], COLORS['fraud']],
                                 hover_data={'is_fraud': ':.2%'},
                                 text_auto='.2%')
    fig_fraud_city_size.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_fraud_city_size.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Топ 20 вендоров по количеству мошеннических транзакций
    top_fraud_vendors = dff[dff['is_fraud'] == True].groupby('vendor').size().nlargest(20).reset_index(name='count')
    fig_top_fraud_vendors = px.bar(top_fraud_vendors, x='vendor', y='count',
                                    title='Топ 20 вендоров по количеству мошеннических транзакций',
                                    labels={'vendor': 'Вендор', 'count': 'Количество мошеннических транзакций'},
                                    color_discrete_sequence=[COLORS['fraud']],
                                    text_auto=True)
    fig_top_fraud_vendors.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_top_fraud_vendors.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Топ 20 городов по количеству мошеннических транзакций
    top_fraud_cities = dff[dff['is_fraud'] == True].groupby('city').size().nlargest(20).reset_index(name='count')
    fig_top_fraud_cities = px.bar(top_fraud_cities, x='city', y='count',
                                  title='Топ 20 городов по количеству мошеннических транзакций',
                                  labels={'city': 'Город', 'count': 'Количество мошеннических транзакций'},
                                  color_discrete_sequence=[COLORS['fraud']],
                                  text_auto=True)
    fig_top_fraud_cities.update_layout(**COMMON_GRAPH_LAYOUT)
    fig_top_fraud_cities.update_traces(marker_line_color='white', marker_line_width=1.5)

    # Топ 10 клиентов по сумме мошенничества
    top_fraud_customers_df = dff[dff['is_fraud'] == True].groupby('customer_id')['amount_converted'].sum().nlargest(
        10).reset_index()
    top_fraud_customers_df.columns = ['ID Клиента', f'Сумма мошенничества ({target_currency})']
    fig_top_fraud_customers = go.Figure(data=[go.Table(
        header=dict(values=list(top_fraud_customers_df.columns),
                    fill_color=COLORS['primary'],
                    align='left',
                    font=dict(color='white', size=14)),
        cells=dict(values=[top_fraud_customers_df['ID Клиента'],
                           top_fraud_customers_df[f'Сумма мошенничества ({target_currency})']],
                   fill_color='lavender',
                   align='left',
                   font=dict(color=COLORS['text'], size=12)))
    ])
    fig_top_fraud_customers.update_layout(title_text=f'Топ 10 клиентов по сумме мошенничества ({target_currency})',
                                          **COMMON_GRAPH_LAYOUT)

    # Возвращаем все фигуры и значения виджетов
    return (fig_overview, fig_fraud_cat, fig_fraud_weekend, fig_fraud_hour, fig_fraud_device,
            fig_amounts, fig_tx_counts, fig_corr, fig_amount_usd_by_country, fig_currency_usage,
            widget_total_transactions_val, widget_total_fraud_amount_val, widget_fraud_percentage_val,
            widget_avg_transaction_amount_val,
            fig_vendor_type_fraud, fig_card_type_fraud, fig_card_present_fraud, fig_outside_home_fraud,
            fig_high_risk_vendor_fraud, fig_fraud_city_size, fig_top_fraud_vendors, fig_top_fraud_cities,
            fig_top_fraud_customers)


if __name__ == '__main__':
    print("Запуск сервера Dash на http://127.0.0.1:8050")
    app.run(debug=True)
