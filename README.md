# GLB -> STEP Microservice

This microservice uses `assimp` to convert GLB -> OBJ, then `FreeCAD` (FreeCADCmd) to convert OBJ -> STEP.

## How it works

1. Client uploads a `.glb` to `/convert`.
2. Server saves file, runs `assimp export input.glb intermediate.obj`.
3. Server runs `FreeCADCmd convert_freecad.py intermediate.obj output.step`.
4. Returns `output.step` as response.

## Build & Run

1. Ensure Docker is installed.
2. `docker compose build --no-cache`
3. `docker compose up -d`
4. POST a multipart/form-data to http://localhost:8000/convert with field `file`.

## Notes & Caveats

- GLB is a mesh format; STEP expects CAD B-Rep data. This pipeline creates a mesh-based STEP (approximation). For true CAD conversions you need source CAD data or a commercial SDK (CAD Exchanger, etc.).
- You may need to tweak tolerances in `makeShapeFromMesh`.
- FreeCAD and assimp versions in the base Ubuntu repo may vary; if you need a specific version build a custom image.
