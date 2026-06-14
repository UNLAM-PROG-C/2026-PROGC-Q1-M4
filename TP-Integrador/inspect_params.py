import pickle
p = pickle.load(open('/app/model_params.pkl', 'rb'))
print('Keys:', list(p.keys()))
for k, v in p.items():
    weights, bias = v['weights'], v['bias']
    print(f'  {k}: W={weights.shape} b={bias.shape}  W=[{weights.min():.4f},{weights.max():.4f}]  b=[{bias.min():.4f},{bias.max():.4f}]')
