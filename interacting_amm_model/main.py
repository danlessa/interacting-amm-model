# %%

from typing import NamedTuple, Dict, List, Optional
from dataclasses import dataclass
from cadCAD_tools import easy_run
from cadCAD_tools.preparation import prepare_params, prepare_state
import plotly.express as px
from cadCAD_tools.types import InitialValue, Param, Signal, StateUpdate, VariableUpdate, ParamSweep
from enum import Enum
from random import random, choice
import pandas as pd
import numpy as np

Wei = int
Percentage = float
Fiat = float


class AMM(NamedTuple):
    label: str
    transaction_fee: Percentage
    gas_fee: Fiat


@dataclass
class PairState():
    reserve_token_1: float
    reserve_token_2: float

    def __add__(self, o):
        if o == {} or o is None:
            return self
        else:
            self.reserve_token_1 += o.reserve_token_1
            self.reserve_token_2 += o.reserve_token_2
        return self
    
    def __mul__(self, o: float):
        self.reserve_token_1 *= o
        self.reserve_token_2 *= o
        return self


class AMM_States(dict):
    def __add__(self, o):
        missing_keys = set(self.keys()) - set(o.keys())
        for key in self.keys():
            self[key] += o.get(key, {})
        for key in missing_keys:
            self[key] = o.get(key)
        return self


UserAction = ('Skip', 'Swap', 'MintBurn')
UserActionDirection = (1, -1)


amms = [AMM('uniswap', 0.003, 20),
        AMM('honeyswap', 0.003, 0.2),
        AMM('curve', 0.0015, 10)]

initial_reserve_1 = 1000
initial_reserve_2 = 5000

pair_states = {amm.label: PairState(initial_reserve_1, initial_reserve_2)
               for amm in amms}

pair_states = AMM_States(pair_states)

initial_state = {
    'market_price_token_1': InitialValue(5.0, Fiat),
    'pair_state': InitialValue(pair_states, AMM_States)
}

params = {
    'amms': Param(amms, list[AMM]),
    'user_action_intensity': Param(0.1, Percentage),
    'arbitrage_intensity': ParamSweep([0.1, 0.9], Percentage),
    'swap_vs_liquidity_preference': Param(0.9, Percentage)
}


def p_arbitrage(params, _2, _3, state) -> Signal:
    """
    Arbitrage on each individual AMM so that it rebound to the market price.
    """
    # Retrieve state and params
    arbitrage_intensity = params['arbitrage_intensity']
    pair_states: AMM_States = state['pair_state']
    market_price = state['market_price']

    delta_pair_state = AMM_States()
    for amm, pair_state in pair_states.items():
        # AMM State
        reserve_1 = pair_state.reserve_token_1
        reserve_2 = pair_state.reserve_token_2
        amm_price = reserve_2 / reserve_1

        # Optimal Token 1 value to make the AMM rebound to the market price
        optimal_value = (reserve_1 - reserve_2) / (amm_price + market_price)

        # Optimal User Action for making the rebound
        optimal_arbitrage = PairState(-optimal_value, optimal_value * amm_price)

        # Randomize the intensity
        real_arbitrage = optimal_arbitrage * random() * arbitrage_intensity

        # Act on it
        delta_pair_state[amm] = real_arbitrage

    return {'delta_pair_state': delta_pair_state}


def p_user_action(params, _2, _3, state) -> Signal:
    """
    Take random user actions
    """
    # Retrieve state and params
    user_action_intensity = params['user_action_intensity']
    swap_vs_liquidity_preference = params['swap_vs_liquidity_preference']
    pair_states: AMM_States = state['pair_state']

    delta_pair_state = AMM_States()
    for amm, pair_state in pair_states.items():
        # AMM State
        token_1_reserve = pair_state.reserve_token_1
        token_2_reserve = pair_state.reserve_token_2

        # Decide if the action is going to be swap or mint/burn
        if random() < swap_vs_liquidity_preference:
            action = 'Swap'
        else:
            action = 'MintBurn'

        # Decide the direction of the swap or mint / burn
        direction: int = choice(UserActionDirection)

        # Intensity in terms of available reserve
        intensity: float = random() * user_action_intensity

        # Set the token amounts based on the sorted direction
        if direction == 1:
            token_amount_1 = token_1_reserve * intensity
            token_amount_2 = token_amount_1 * token_2_reserve / token_1_reserve
        else:
            token_amount_2 = token_2_reserve * intensity
            token_amount_1 = token_amount_2 * token_1_reserve / token_2_reserve

        # Take action
        if action == 'Swap':
            token_1_reserve = -1 * token_amount_1 * direction
            token_2_reserve = token_amount_2 * direction
        elif action == 'MintBurn':
            token_1_reserve = token_amount_1 * direction
            token_2_reserve = token_amount_2 * direction
        else:
            token_1_reserve = 0
            token_2_reserve = 0
        
        # Append the AMM action
        delta_pair_state[amm] = PairState(token_1_reserve, token_2_reserve)
    return {'delta_pair_state': delta_pair_state}


def s_pair_state(_1, _2, _3, state, signal) -> VariableUpdate:
    # State and signals
    new_pair_state: AMM_States = state['pair_state']
    delta_pair_state: AMM_States = signal['delta_pair_state']

    # Sum the change on the pair states
    for amm_label, amm_pair_state in delta_pair_state.items():
        new_pair_state[amm_label] += amm_pair_state

    # Assign new variable
    return ('pair_state', new_pair_state)


def brownian_motion(variable) -> StateUpdate:
    def suf(_1, _2, _3, state, _5) -> VariableUpdate:
        x = state[variable]
        raw_percent_change = (2 * random() - 1)
        percent_change = raw_percent_change * 0.1
        dx = x * percent_change
        new_x = x + dx
        return (variable, new_x)
    return suf


def p_market_price(_1, _2, _3, state) -> Signal:
    """
    Retrieve the market price as proxied by the mean value of the AMMs
    as well as its associated volatility
    """
    pair_states: AMM_States = state['pair_state']
    prices = []
    for _, pair_state in pair_states.items():
        amm_price = pair_state.reserve_token_2 / pair_state.reserve_token_1
        prices.append(amm_price)
    return {'market_price': np.mean(prices),
            'market_price_volatility': np.std(prices)}

def generic_suf(variable) -> StateUpdate:
    def suf(params, substep, history, state, signal):
        return (variable, signal[variable])
    return suf

timestep_block = [
    {
        'label': 'Market Movements',
        'policies': {
            'market_price': p_market_price

        },
        'variables': {
            'market_price': generic_suf('market_price'),
            'market_price_volatility': generic_suf('market_price_volatility'),
        }
    },
    {
        'label': 'AMM User Actions',
        'policies': {

            'user_action': p_user_action,
            'arbitrage': p_arbitrage
        },
        'variables': {
            'pair_state': s_pair_state
        }
    },

]

N_timesteps = 100
N_samples = 5
initial_state = prepare_state(initial_state)
params = prepare_params(params)

results = (easy_run(initial_state,
                    params,
                    timestep_block,
                    N_timesteps,
                    N_samples,
                    assign_params=False)
           .reset_index())

# %%
results.pair_state
# %%
results.market_price_token_1
# %%
px.line(results,
        x='timestep',
        y='market_price',
        facet_col='subset',
        line_group='run')


# %%
px.line(results,
        x='timestep',
        y='market_price_volatility',
        facet_col='subset',
        line_group='run')
# %%
print(results.pair_state.iloc[-1])

# %%

for amm in amms:
    amm_df = pd.DataFrame(results.pair_state
                          .map(lambda s: s[amm.label])
                          .tolist()
                          )

    amm_df = amm_df.add_prefix(f"{amm.label}_")
    results = results.join(amm_df)

# %%
y_cols = [f"{amm.label}_reserve_token_1" for amm in amms]

px.line(results,
        x='timestep',
        y=y_cols,
        facet_col='subset',
        line_group='run')

# %%
