import dash
from dash import html, dcc, Input, Output, callback, dash_table 
import yfinance as yf
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import pandas as pd
import requests
from prophet import Prophet
from datetime import date, timedelta, datetime
import os

#################### FUNCTIONS ####################
def create_indices_charts(): 
    # end def    # Download the data from yahoo finance
    tickers = ['^VIX', '^GSPC', '^IXIC', 'GLD']
    ticker_names = ['VIX Volatility Index', 'S & P 500 Index', 'NASDAQ Index', 'Gold ETF']

    data = yf.download(tickers, period='1y', interval='1d', group_by='ticker', rounding=True)

    # Calculate the average close price for each index
    avg_prices = {ticker: data[ticker]['Close'].mean() for ticker in tickers}

    # Create subplots
    fig = make_subplots(rows=1, cols=4, subplot_titles=ticker_names)

    # Add traces for each index
    for i, ticker in enumerate(tickers, start=1):
        fig.add_trace(
            go.Scatter(x=data[ticker].index, y=data[ticker]['Close'], name=ticker_names[i-1]),
            row=1, col=i
        )
        # Add average line
        fig.add_hline(
            y=avg_prices[ticker], 
            line_dash="dash", 
            annotation_text=f"Avg: ${avg_prices[ticker]:.2f}",
            annotation_position="bottom right",
            annotation_bgcolor="grey",
            row=1, col=i
        )

    # Update layout
    fig.update_layout(
        template='plotly_dark',
        title='Market Watch 📈',
        title_font_family="Rockwell",
        title_font_size=24,
        title_x=0.5,
        width=1500,  # Adjusted for 4 charts
        height=400,
        margin=dict(l=10, r=15, t=90, b=20),
        showlegend=False
    )
    fig.update_layout(hoverlabel=dict(font_size=12, font_family="Rockwell", bgcolor='black', font_color='white'))

    # Update xaxes and yaxes
    for i in range(1, 5):
        fig.update_xaxes(title='', showgrid=True, showticklabels=True, row=1, col=i)
        fig.update_yaxes(title='', showgrid=False, showticklabels=False, row=1, col=i)

    # Show figure
    return fig

def load_and_combine_tickers():
    # get the Ticker column from the dividend excel file
    dividend_tickers = pd.read_excel('data/Dividend_Dashboard.xlsx', sheet_name='current_holdings', usecols='G') 
    tickers = ['CAD=X', 'GLD', 'SPLG', 'BTC-USD', 'ETH-USD']
    # convert divedend tickers to a list
    dividend_tickers = dividend_tickers['Ticker'].tolist()
    # sort the list
    dividend_tickers.sort()
    tickers = tickers + dividend_tickers
    return tickers

# get the data from yahoo finance
def get_data(symbol):
    # todo: add a doc string
    # get data from yahoo finance to use
    symbol_data = yf.download(symbol, period='max', rounding=False, prepost=True)
    return symbol_data

# splice the data when povided a date best to do a forecast on 2 years of data
def splice_data(df, date, query=False, query_on=''):
    # todo: add a doc string
    if query:
        return df.query(f'{query_on} >= "{date}"')
    return df.loc[date:]    

def forcasting_preparation(df):
    # todo: add a doc string
    df = df.reset_index()
    return df[['Date', 'Close']]
        
# use prophet to forecast the data
def forecast_data(data):
    # todo: add a doc string
    data = data.rename(columns={'Date': 'ds', 'Close': 'y'})
    model = Prophet()
    model.fit(data)
    future = model.make_future_dataframe(periods=90, freq='D')
    forecast = model.predict(future)
    return forecast

def process_forecasted_data(forecast_df):
    # todo: add a doc string
    df = forecast_df.copy()
    # keep only needed columns in the forecast dataframe
    df = df[['ds', 'yhat', 'yhat_lower', 'yhat_upper', 'trend']]  
    # smooth out the prediction lines
    df['predicted_price'] = df['yhat'].rolling(window=7).mean()
    df['upper_band'] = df['yhat_upper'].rolling(window=7).mean()
    df['lower_band'] = df['yhat_lower'].rolling(window=7).mean()
    return df

def plotly_visualize_forecast(symbol, data, forcast_processed, width=1400, height=800):
    # todo: add a doc string
    #  get timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d @ %H:%M:%S")
    date_buttons = [{'count': 9, 'label': '6M', 'step': "month", 'stepmode': "todate"},
                    {'count': 6, 'label': '3M', 'step': "month", 'stepmode': "todate"},
                    {'count': 4, 'label': '1M', 'step': "month", 'stepmode': "todate"}]
    # create the plotly chart
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=data.index, open=data.Open, high=data.High, low=data.Low, close=data.Close, name='Candlestick', increasing_line_color='#F6FEFF', decreasing_line_color='#1CBDFB'))
    
    # update the layout of the chart with the buttons and timestamp along with some kwargs
    fig.update_layout(  
        {'xaxis':
            {'rangeselector': {'buttons': date_buttons, 
                                'bgcolor': '#444654', 
                                'activecolor': '#1E82CD',
                                'bordercolor': '#444654',
                                'font': {'color': 'white'}}
            }
        },
            width=width, height=height, xaxis_rangeslider_visible=False, 
            paper_bgcolor='#202123', plot_bgcolor='#202123', font=dict(color='white', size=12),
            font_size=14, font_family="Rockwell", title_font_family="Rockwell", title_font_size=24
    )
    
    #  update the layout of the chart with the title and axis labels
    fig.update_layout( 
        {'annotations': [{  "text": f"This graph was last generated on {timestamp}", 
                            "showarrow": False, "x": 0.55, "y": 1.05, "xref": "paper", "yref": "paper"}]},
    )

    fig.update_layout( 
        {'title': {'text':f'{symbol} Price Chart', 'x': 0.5, 'y': 0.95}},
        yaxis=dict(title='Price', gridcolor='#444654'), xaxis=dict(gridcolor='#444654')
    )
    # Update y-axes to include dollar sign
    fig.update_yaxes(tickprefix="$")
    
    # add the predicted price and trend lines to the chart
    fig.add_trace(go.Scatter(x=forcast_processed.ds, y=forcast_processed.predicted_price, line=dict(color='#B111D6', width=1), name='Predicted Price'))
    fig.add_trace(go.Scatter(x=forcast_processed.ds, y=forcast_processed.trend, line=dict(color='#0074BA', width=1), name='Predicted Trend'))
    fig.add_trace(go.Scatter(x=forcast_processed.ds, y=forcast_processed.upper_band, line=dict(color='#1E82CD', width=2), name='upper_band'))
    fig.add_trace(go.Scatter(x=forcast_processed.ds, y=forcast_processed.lower_band, line=dict(color='#1E82CD', width=2), name='lower_band'))
    return fig

def process_chart_pipeline(symbol):
    data = get_data(symbol)
    # get date 2 years ago
    two_years_ago = TODAYS_DATE - timedelta(days=730)
    data = splice_data(data, two_years_ago)
    forcasting_prep = forcasting_preparation(data)
    forecast = forecast_data(forcasting_prep)
    processed_forecast = process_forecasted_data(forecast)

    # visulize the data 
    fig = plotly_visualize_forecast(symbol, data, processed_forecast)
    return fig

def fetch_dividend_data(ticker, api_key):
    """
    Fetches the dividend data for a given stock ticker using the Polygon API.

    Parameters:
    ticker (str): The stock ticker symbol.
    api_key (str): Your Polygon API key.

    Returns:
    DataFrame: A DataFrame containing dividend information.
    """
    # Format the URL for the API request, including the ticker symbol and API key
    url = f'https://api.polygon.io/v3/reference/dividends?ticker={ticker}&limit=1&apiKey={api_key}'

    # Make a GET request to the API and parse the JSON response
    response = requests.get(url).json()

    # Check if the response contains results and return an empty DataFrame if not
    if not response.get('results'):
        return pd.DataFrame()

    # Convert the extracted data into a Pandas DataFrame
    dividend_df = pd.DataFrame(response['results'])

    # Select and retain only the specified columns in the DataFrame
    dividend_df = dividend_df[['ticker', 'cash_amount', 'ex_dividend_date', 'frequency', 'pay_date']]

    return dividend_df

def create_table(ticker):
    try:
        table_df = fetch_dividend_data(ticker,API_KEY)
    except:
        table_df = pd.DataFrame()
    return dash_table.DataTable(
                id='dividend_table',
                    columns=[
                        {
                            "name": i, 
                            "id": i,
                            "type": "numeric",
                            "format": MONEY_FORMAT if i in ['cash_amount'] else None
                        } for i in table_df.columns],
                    data=table_df.to_dict('records'),
                    cell_selectable=False,
                    style_header={'textAlign': 'center', 'backgroundColor': '#1E1E1E', 'fontWeight': 'bold', 'color': 'white'},
                    style_cell_conditional=[
                        {
                            'if': { 'column_id': ['ticker', 'frequency', 'cash_amount', 'ex_dividend_date', 'pay_date'] },
                            'textAlign': 'center',
                        }
                    ],
                    style_data_conditional=[
                        {
                            'if': {'row_index': 'odd'},
                            'backgroundColor': '#1E1E1E',
                            'color': 'white',
                            'fontWeight': 'bold'
                        },
                        {
                            'if': {'row_index': 'even'},
                            'backgroundColor': '#adaaaa',  # A light grey for even rows
                            'color': 'black',
                            'fontWeight': 'bold'
                        },
                    ],
                    style_as_list_view=False,
                    style_table={'overflowX': 'scroll', 'width': '100%'}, 
            )

#################### CONSTANTS ####################
TICKERS = load_and_combine_tickers()
TODAYS_DATE = date.today()
API_KEY = os.environ.get('POLYGON_API_KEY')
MONEY_FORMAT = dash_table.FormatTemplate.money(2)


dash.register_page(__name__, path='/market_watch', name='Market Watch 📈')

#################### PAGE LAYOUT ####################
layout = html.Div(children=[
        html.Br(),
        html.Div(children=[
            dcc.Graph(figure=create_indices_charts()),
        ], style={'textAlign': 'center', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'flexDirection': 'column', 'width': '100%'}),
        html.Hr(style={'color': 'white'}),
        html.Div([
            html.H4('Select Ticker:', style={'paddingLeft': '25px'}),
            dcc.Dropdown(id='ticker_dropdown', 
                         options=[{'label': 'USD/CAD', 'value': ticker} if ticker == 'CAD=X' else {'label': ticker, 'value': ticker} for ticker in TICKERS],
                         value='CAD=X', 
                         clearable=False, 
                         style={'width': '32%', 'paddingLeft': '25px', 'display': 'inline-block'})
        ]),
        html.Div(children=[
            dcc.Graph( id='ticker_chart', figure=process_chart_pipeline('CAD=X')),
        ], style={'textAlign': 'center', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'flexDirection': 'column', 'width': '100%', 'marginBottom': '10px'}),
        html.Div(id='div_table', children=[
            
        ], style={'textAlign': 'center', 'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'flexDirection': 'column', 'width': '100%'}),
        dcc.Interval(
            id='interval-component',
            interval=15*60*1000, # in milliseconds = 30 minutes
            n_intervals=0
        )
        
])

#################### CALLBACKS ####################
@callback(
    Output('ticker_chart', 'figure'), 
    Output('div_table', 'children'),
    Input('ticker_dropdown', 'value'),
    Input('interval-component', 'n_intervals'),
    # do not run the callback if the ticker is not changed
    prevent_initial_call=True
    )
def update_chart(ticker, n):
    fig = process_chart_pipeline(ticker)
    table = create_table(ticker)
    return fig, table

