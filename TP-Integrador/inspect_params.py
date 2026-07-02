import pickle

MODEL_PARAMS_PATH = '/app/model_params.pkl'
WEIGHTS_KEY = 'weights'
BIAS_KEY = 'bias'

with open(MODEL_PARAMS_PATH, 'rb') as f:
  p = pickle.load(f)

print('Keys:', list(p.keys()))
for k, v in p.items():
  weights, bias = v[WEIGHTS_KEY], v[BIAS_KEY]
  print(f'  {k}: W={weights.shape} b={bias.shape}  '
        f'W=[{weights.min():.4f},{weights.max():.4f}]  '
        f'b=[{bias.min():.4f},{bias.max():.4f}]')
