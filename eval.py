import pandas as pd
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from trading_env import StockTradingEnv
from agents import SimpleAvgEnsembleAgent, A2CAgent, PPOAgent, A2CAgent, DDPGAgent, TD3Agent, SACAgent, WeightedAvgEnsembleAgent, MetaRfAgent
import matplotlib.pyplot as plt
from stable_baselines3.common.vec_env import DummyVecEnv
from sklearn.ensemble import RandomForestRegressor

def add_technical_indicators(df):
    df = df.copy()
    # MACD and Signal
    df.loc[:, 'EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df.loc[:, 'EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df.loc[:, 'MACD'] = df['EMA12'] - df['EMA26']
    df.loc[:, 'Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss
    df.loc[:, 'RSI'] = 100 - (100 / (1 + rs))
    
    # CCI
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    sma_tp = tp.rolling(window=20).mean()
    mean_dev = tp.rolling(window=20).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    df.loc[:, 'CCI'] = (tp - sma_tp) / (0.015 * mean_dev)
    
    # ADX
    high_diff = df['High'].diff()
    low_diff = df['Low'].diff()
    df.loc[:, '+DM'] = np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0)
    df.loc[:, '-DM'] = np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0)
    tr = pd.concat([df['High'] - df['Low'], np.abs(df['High'] - df['Close'].shift(1)), np.abs(df['Low'] - df['Close'].shift(1))], axis=1).max(axis=1)
    atr = tr.ewm(span=14, adjust=False).mean()
    df.loc[:, '+DI'] = 100 * (df['+DM'].ewm(span=14, adjust=False).mean() / atr)
    df.loc[:, '-DI'] = 100 * (df['-DM'].ewm(span=14, adjust=False).mean() / atr)
    dx = 100 * np.abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI'])
    df.loc[:, 'ADX'] = dx.ewm(span=14, adjust=False).mean()

    # Drop NaN values
    df.dropna(inplace=True)

    # Keep only the relevant columns
    df = df[['Open', 'High', 'Low', 'Close', 'Volume', 'MACD', 'Signal', 'RSI', 'CCI', 'ADX']]

    return df

def test_agent(env, agent, stock_data, n_tests, visualize=False):
    """
    Test a single agent and track performance metrics, with an option to visualize the results.

    Parameters:
    - env: The trading environment.
    - agent: The agent to be tested.
    - stock_data: Data for the stocks in the environment.
    - n_tests: Number of tests to run. This is the total number of steps you take on the environment. Should be the length of the test set.
    - visualize: Boolean flag to enable or disable visualization (default: False).

    Returns:
    - A dictionary containing steps, balances, net worth, and shares held.
    """
    # Initialize metrics tracking
    metrics = {
        'steps': [], # steps?
        'balances': [],
        'net_worth': [],
        'shares_held': {ticker: [] for ticker in stock_data.keys()},
        'actions': [],
        'rewards': []
    }

    # Reset the environment before starting the tests
    obs = env.reset()

    # Is one iteration a day?
    for i in range(n_tests):
        metrics['steps'].append(i)
        action = agent.predict(obs)
        metrics['actions'].append(action)
        obs, rewards, done, infos = env.step(action)
        metrics['rewards'].append(rewards)
        if visualize:
            env.render()

        # Track metrics
        metrics['balances'].append(env.get_attr('balance')[0])
        metrics['net_worth'].append(env.get_attr('net_worth')[0])
        env_shares_held = env.get_attr('shares_held')[0]

        # Update shares held for each ticker
        for ticker in stock_data.keys():
            metrics['shares_held'][ticker].append(env_shares_held[ticker])
            
        if done:
            obs = env.reset()
            
    return metrics

def visualize_multiple_portfolio_net_worth(steps, net_worths_list, labels, dji_test_data=None):
    plt.figure(figsize=(12, 6))
    for i, net_worths in enumerate(net_worths_list):
        plt.plot(steps, net_worths, label=labels[i])
    
    if dji_test_data is not None:
        plt.plot(steps, dji_test_data, label="^DJI")

    plt.title('Net Worth Over Time')
    plt.xlabel('Steps')
    plt.ylabel('Net Worth')
    plt.legend()
    plt.show()

def test_all_agents(agents, test_data, test_vix, n_tests=1000):
    metrics = {}
    for agent_name, agent in agents.items():
        # create a new test environment for testing each agent
        env = DummyVecEnv([lambda: StockTradingEnv(test_data, test_vix)])
        print(f"Testing {agent_name}...")
        metrics[agent_name] = test_agent(env, agent, test_data, n_tests=n_tests, visualize=True)
        print(f"Done testing {agent_name}!")
    
    print('-'*50)
    print('All agents tested!')
    print('-'*50)

    
    return metrics

def calc_weights(validation_results, initial_balance):
    # initialize weights to be the reward over validation set
    weights = {}
    for agent in list(validation_metrics.keys()):
        # only consider the agents that went positive in the ensemble
        if validation_metrics[agent]['net_worth'][-1] > initial_balance:
            weights[agent] = validation_metrics[agent]['net_worth'][-1]

    # normalize weights?
    total_reward = sum(weights.values())
    for agent in list(weights.keys()):
        weights[agent] = weights[agent] / total_reward
    return weights


# Stocks from the Dow 30
tickers = [
    'MMM', 'AMZN', 'AXP', 'AMGN', 'AAPL', 'BA', 'CAT', 'CVX', 'CSCO', 'KO',
    'GS', 'HD', 'HON', 'IBM', 'JNJ', 'JPM', 'MCD', 'MRK', 'MSFT', 'NKE',
    'NVDA', 'PG', 'CRM', 'SHW', 'TRV', 'UNH', 'VZ', 'V', 'WMT', 'DIS'
]

# Get the data from the CSV files
stock_data = {}
for ticker in tickers:
    df = pd.read_csv(f'data_current/{ticker}.csv', index_col='Date', parse_dates=True)
    stock_data[ticker] = df

vix_data = pd.read_csv(f'data_current/^VIX.csv', index_col='Date', parse_dates=True)

dji_data = pd.read_csv(f'portfolio_value.csv', index_col='Date', parse_dates=True)

# split the data into training, validation and test sets
training_data_time_range = ('2009-01-01', '2016-12-31') # 70% #  '2009-06-01', '2020-03-18' 7 years
validation_data_time_range = ('2017-01-01', '2017-12-31') # 15% '2020-03-19', '2022-07-11')
test_data_time_range = ('2018-01-01', '2022-05-08') # 15% '2022-07-12', '2024-11-01' 5 1/2 years


# split the data into training, validation and test sets
training_data = {}
validation_data = {}
test_data = {}

# split the data dictionary into subdictionaries for training, validation, testing
for ticker, df in stock_data.items():
    training_data[ticker] = df.loc[training_data_time_range[0]:training_data_time_range[1]]
    validation_data[ticker] = df.loc[validation_data_time_range[0]:validation_data_time_range[1]]
    test_data[ticker] = df.loc[test_data_time_range[0]:test_data_time_range[1]]

vix_training_data = vix_data.loc[training_data_time_range[0]:training_data_time_range[1]]
vix_validation_data = vix_data.loc[validation_data_time_range[0]:validation_data_time_range[1]]
vix_test_data = vix_data.loc[test_data_time_range[0]:test_data_time_range[1]]

dji_test_data = dji_data.loc[test_data_time_range[0]:test_data_time_range[1]]

# add technical indicators to the training data for each stock
for ticker, df in training_data.items():
    training_data[ticker] = add_technical_indicators(df)

# add technical indicators to the validation data for each stock
for ticker, df in validation_data.items():
    validation_data[ticker] = add_technical_indicators(df)

# add technical indicators to the test data for each stock
for ticker, df in test_data.items():
    test_data[ticker] = add_technical_indicators(df)

# print shape of training, validation and test data
ticker = 'MMM'
print(f'Training data shape for {ticker}: {training_data[ticker].shape}')
print(f'Validation data shape for {ticker}: {validation_data[ticker].shape}')
print(f'Test data shape for {ticker}: {test_data[ticker].shape}')

print(test_data[ticker].head())
print(len(test_data))

# load the models
ppo_agent = PPOAgent(load=True)
a2c_agent = A2CAgent(load=True)
ddpg_agent = DDPGAgent(load=True)
sac_agent = SACAgent(load=True)
td3_agent = TD3Agent(load=True)

#agents for validation, 
#n_tests = 559 even though length of original validation is 582 because adding adding TAs drops the beginning of the df
n_tests = 230 
initial_balance = 10000
validation_agents = {
    'PPO Agent': ppo_agent,
    'A2C Agent': a2c_agent,
    'DDPG Agent': ddpg_agent, 
    'SAC Agent': sac_agent,
    'TD3 Agent': td3_agent
}

# calculate weights and organize models for weigted average ensemble 
validation_metrics = test_all_agents(validation_agents, validation_data, vix_validation_data, n_tests=n_tests)
validation_weights = calc_weights(validation_metrics, initial_balance)

for agent in list(validation_agents.keys()):
    print("Agent: ", agent, " final net worth: ", validation_metrics[agent]['net_worth'][-1])

print(validation_weights)

validation_net_worth = [validation_metrics[agent]['net_worth'] for agent in list(validation_agents.keys())]

# for agent in list(validation_agents.keys()):
#     print("Agent: ", agent, " net worth: ", validation_metrics[agent]['net_worth'])
visualize_multiple_portfolio_net_worth(validation_metrics['PPO Agent']['steps'], validation_net_worth, list(validation_agents.keys()))

# META ENSEMBLE ATTEMPT-------------------
training_tests = 1993
training_metrics = test_all_agents(validation_agents, training_data, vix_training_data, n_tests = training_tests)
# combine all the rewards
combined_rewards = []
for i in range(training_tests):
    combined_rewards.append([])
    for agent in list(validation_agents.keys()):
        combined_rewards[i].append(training_metrics[agent]['rewards'][i])

# get the best action at each step
best_actions = []
for i in range(len(combined_rewards)):
    actions = [training_metrics['PPO Agent']['actions'][i], training_metrics['A2C Agent']['actions'][i], training_metrics['DDPG Agent']['actions'][i],
               training_metrics['SAC Agent']['actions'][i], training_metrics['TD3 Agent']['actions'][i]]
    best_action = actions[np.argmax([combined_rewards[i]])]  # Choose action with max reward
    best_actions.append(best_action)

# Train meta-model using agent actions as features and best_actions as targets
meta_features = np.column_stack((training_metrics['PPO Agent']['actions'], training_metrics['A2C Agent']['actions'], training_metrics['DDPG Agent']['actions'],
               training_metrics['SAC Agent']['actions'], training_metrics['TD3 Agent']['actions']))
meta_labels = np.array(best_actions)  # Target is now the best action

meta_model = RandomForestRegressor(n_estimators=50, random_state=42)
meta_features = meta_features.reshape(meta_features.shape[0], -1)
meta_labels = meta_labels.reshape(meta_labels.shape[0], -1)
print("Meta Labels Shape: ", meta_labels.shape)
print("Meta Features Shape: ", meta_features.shape)
meta_model.fit(meta_features, meta_labels)
print("Trained Random forest!")

#--------------------------------------

weighted_avg_models = {}
for agent in list(validation_weights.keys()):
    weighted_avg_models[agent] = validation_agents[agent].model

simple_avg_agent = SimpleAvgEnsembleAgent(ppo_agent.model, a2c_agent.model, ddpg_agent.model, sac_agent.model, td3_agent.model)
weighted_avg_agent = WeightedAvgEnsembleAgent(weighted_avg_models, validation_weights)
meta_agent = MetaRfAgent(ppo_agent.model, a2c_agent.model, ddpg_agent.model, sac_agent.model, td3_agent.model, meta_model)

test_agents = {
    'PPO Agent': ppo_agent,
    'A2C Agent': a2c_agent,
    'DDPG Agent': ddpg_agent, 
    'SAC Agent': sac_agent,
    'TD3 Agent': td3_agent,
    "Simple Avg Ensemble": simple_avg_agent,
    "Weighted Avg Ensemble": weighted_avg_agent,
    "Meta Agent": meta_agent
}

n_tests = 1074 # steps in test

test_metrics = test_all_agents(test_agents, test_data, vix_test_data, n_tests=n_tests)

test_net_worth = [test_metrics[agent]['net_worth'] for agent in list(test_agents.keys())]
cumulative_rewards = {}
max_draw = {}
for agent in list(test_agents.keys()):
    cumulative_rewards[agent] = (test_metrics[agent]['net_worth'][-1] - test_metrics[agent]['net_worth'][0]) / test_metrics[agent]['net_worth'][0]
    # Step 1: Calculate the running maximum
    running_max = np.maximum.accumulate(test_metrics[agent]['net_worth'])

    # Step 2: Calculate drawdowns
    drawdowns = (test_metrics[agent]['net_worth'] - running_max) / running_max

    # Step 3: Find the maximum drawdown
    max_drawdown = np.min(drawdowns)

    max_draw[agent] = max_drawdown

print(dji_test_data.head(21)) # dropping the beginning for TAs in test data
dji_prices = dji_test_data['Portfolio Value'].to_numpy()

dji_prices = dji_prices[21:] # dropping the beginning for TAs in test  data

cumulative_rewards["^DJI"] = (dji_prices[-1] - dji_prices[0]) / dji_prices[0]

# Step 1: Calculate the running maximum
running_max = np.maximum.accumulate(dji_prices)

# Step 2: Calculate drawdowns
drawdowns = (dji_prices - running_max) / running_max

# Step 3: Find the maximum drawdown
max_drawdown = np.min(drawdowns)

max_draw["^DJI"] = max_drawdown

print("Cumulative Rewards: ")
print(cumulative_rewards)
print("Max DrawDown: ")
print(max_draw)

visualize_multiple_portfolio_net_worth(test_metrics['PPO Agent']['steps'], test_net_worth, list(test_agents.keys()), dji_prices)