#!/usr/bin/env bash
set -Eeuo pipefail
ENGINE=/tmp/forgeguard_identity.engine
python3 - "$ENGINE" <<'PY'
import os, sys, tensorrt as trt
path=sys.argv[1]
logger=trt.Logger(trt.Logger.WARNING)
builder=trt.Builder(logger)
network=builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
x=network.add_input('x', trt.float32, (1,16))
y=network.add_identity(x).get_output(0)
network.mark_output(y)
config=builder.create_builder_config()
config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE,64*1024*1024)
blob=builder.build_serialized_network(network,config)
if blob is None: raise SystemExit('Engine build failed')
open(path,'wb').write(blob)
print('Engine bytes',os.path.getsize(path))
PY
TRTEXEC=$(command -v trtexec || true)
[ -n "$TRTEXEC" ] || TRTEXEC=/usr/src/tensorrt/bin/trtexec
"$TRTEXEC" --loadEngine="$ENGINE" --warmUp=200 --duration=3 --iterations=50 --useCudaGraph
