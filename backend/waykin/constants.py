import numpy as np

CRS_METRIC = "EPSG:32612"                      # UTM 12N (Edmonton)
DEMO_BBOX = (-113.535, 53.510, -113.480, 53.530)  # (west, south, east, north): U of A + Old Strathcona.
                                               # The team lead may change it before the H6 graph build. Never after.
WALK_SPEED_M_PER_MIN = 80.0                    # 4.8 km/h
MIN_EDGE_MINUTES = 1e-3                        # no zero weights in csgraph
SNAP_MAX_M = 250.0
RADII_M = (50, 100, 200)
DEFAULT_RADIUS_M = 100
WINDOW_DAYS = 90
N_DRAWS = 500
SEED = 20261106
DIRICHLET_KAPPA = 5.0
GAMMA_PRIOR_SHAPE = 0.5                        # posterior shape = count + 0.5, rate = 1
LAMBDA_GRID = (0.0,) + tuple(float(x) for x in np.geomspace(0.05, 50.0, 11).round(4))  # minutes per attributed report, 12 values
MAX_EXTRA_TIME = 0.25                          # at most 25% slower than fastest
MIN_REDUCTION = 0.15                           # at least 15% lower than fastest ...
MIN_DRAW_SHARE = 0.90                          # ... in at least 90% of draws
MIN_REPORTS_FOR_SIGNAL = 3.0                   # below this the result is thin_data
BALANCED_MIN_REDUCTION = 0.05
UNITS = "reported incidents attributed to segments along this route, last 90 days"
DISCLAIMER = ("Counts of reported incidents near street segments, from public police data. "
              "They describe the past, not what will happen on your walk. "
              "Not for comparing neighbourhoods.")
RELAY_MAX_MSG_BYTES = 4096
RELAY_MAX_MSGS_PER_SEC = 4
RELAY_MAX_VIEWERS = 5
JOURNEY_TTL_MIN_DEFAULT = 120
JOURNEY_TTL_MIN_MAX = 240
