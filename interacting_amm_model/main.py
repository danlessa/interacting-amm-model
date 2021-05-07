# %%
import plotly.express as px
import pandas as pd

from cadCAD_tools import easy_run

from .model import initial_state, params, timestep_block, N_timesteps, N_samples
from .model import amms

results = (easy_run(initial_state,
                    params,
                    timestep_block,
                    N_timesteps,
                    N_samples,
                    assign_params=False)
           .reset_index())

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
