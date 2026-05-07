import numpy as np
import os

arr = np.array([1, 2, 3, 4, 5])
print("Array:", arr)
print("Promedio lol:", np.mean(arr))

# Escribir en /ipc
ipc_dir = "/ipc"
os.makedirs(ipc_dir, exist_ok=True)

output_file = os.path.join(ipc_dir, "python_output.txt")
with open(output_file, "w") as f:
    f.write(f"Promedio: {np.mean(arr)}\n")
    f.write(f"Array: {arr}\n")

print(f"Escrito en {output_file}")