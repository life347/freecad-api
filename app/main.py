from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import shutil
import os
import uuid
import subprocess
import zipfile
from pathlib import Path


app = FastAPI(title="GLB -> STEP converter (Assimp + FreeCAD)")


STORAGE = Path("/storage")
STORAGE.mkdir(parents=True, exist_ok=True)


@app.post('/convert')
async def convert(file: UploadFile = File(...)):
# Accept only .glb
    if not file.filename.lower().endswith('.glb'):
        raise HTTPException(status_code=400, detail='Only .glb files are accepted')


    job_id = str(uuid.uuid4())
    job_dir = STORAGE / job_id
    job_dir.mkdir()


    glb_path = job_dir / 'input.glb'
    with glb_path.open('wb') as f:
        shutil.copyfileobj(file.file, f)


    # Step 1: convert GLB -> OBJ using assimp (assimp export)
    obj_path = job_dir / 'intermediate.obj'
    try:
        subprocess.run(['assimp', 'export', str(glb_path), str(obj_path)], check=True, timeout=60)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f'Assimp conversion failed: {e}')
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail='Assimp conversion timed out')


    # Step 2: call FreeCADCmd to convert OBJ -> STEP with ALL geometry
    step_path = job_dir / 'output.step'
    try:
        # Set environment for headless operation
        env = os.environ.copy()
        env['DISPLAY'] = ':99'
        env['QT_QPA_PLATFORM'] = 'offscreen'
        
        # FreeCAD script to convert ALL faces from OBJ
        script_content = f"""
import sys
import os
print("Starting FreeCAD conversion...")

try:
    import FreeCAD
    import Mesh
    import Part
    
    input_path = '{str(obj_path)}'
    output_path = '{str(step_path)}'
    
    print(f"Loading mesh from: {{input_path}}")
    
    # Create document
    doc = FreeCAD.newDocument()
    
    # Load mesh
    mesh = Mesh.Mesh(input_path)
    print(f"Loaded mesh with {{mesh.CountFacets}} facets")
    
    if mesh.CountFacets == 0:
        print("ERROR: No mesh data found")
        sys.exit(1)
    
    # Convert ALL mesh geometry to STEP
    print("Converting ALL mesh faces to shape...")
    
    # Get the mesh topology (vertices, faces)
    topo = mesh.Topology
    vertices = topo[0]  # List of vertices
    faces = topo[1]     # List of face indices
    
    print(f"Processing ALL {{len(faces)}} faces from {{len(vertices)}} vertices")
    
    # Create faces from ALL topology - no limits
    shape_faces = []
    error_count = 0
    
    # Process every single face
    for i in range(len(faces)):
        try:
            face_indices = faces[i]
            if len(face_indices) >= 3:
                # Get first 3 vertices for triangle
                v1 = FreeCAD.Vector(vertices[face_indices[0]])
                v2 = FreeCAD.Vector(vertices[face_indices[1]]) 
                v3 = FreeCAD.Vector(vertices[face_indices[2]])
                
                # Create triangular face
                wire = Part.makePolygon([v1, v2, v3, v1])
                face = Part.Face(wire)
                shape_faces.append(face)
        except Exception as face_err:
            error_count += 1
            continue
        
        # Progress indicator for large meshes
        if i % 5000 == 0 and i > 0:
            print(f"Processed {{i}}/{{len(faces)}} faces...")
    
    print(f"Created {{len(shape_faces)}} valid faces ({{error_count}} errors)")
    
    if len(shape_faces) == 0:
        print("ERROR: No valid faces created")
        sys.exit(1)
    
    # Create compound shape from ALL faces
    print("Creating compound from all faces...")
    compound = Part.makeCompound(shape_faces)
    print(f"Created compound with {{len(shape_faces)}} faces")
    
    # Create a Part object in the document and assign the shape
    part_obj = doc.addObject("Part::Feature", "ConvertedMesh")
    part_obj.Shape = compound
    
    # Recompute the document to ensure the part is properly created
    print("Recomputing document...")
    doc.recompute()
    
    print("Exporting complete geometry to STEP format...")
    # Export using the Part object
    Part.export([part_obj], output_path)
    
    print("Cleaning up...")
    FreeCAD.closeDocument(doc.Name)
    
    if os.path.exists(output_path):
        # Check if file has actual content
        file_size = os.path.getsize(output_path)
        print(f"SUCCESS: Created {{output_path}} ({{file_size}} bytes)")
        
        # Read a few lines to verify content
        with open(output_path, 'r') as f:
            lines = f.readlines()
            print(f"STEP file has {{len(lines)}} lines")
            print(f"Converted {{len(shape_faces)}}/{{len(faces)}} faces to STEP")
    else:
        print("ERROR: Output file not created")
        sys.exit(1)
        
except Exception as e:
    import traceback
    print(f"ERROR: {{e}}")
    traceback.print_exc()
    sys.exit(1)
"""
        
        result = subprocess.run(['FreeCADCmd', '-c', script_content], 
                               check=True, timeout=300, env=env, capture_output=True, text=True)
        print("FreeCAD output:", result.stdout)
        if result.stderr:
            print("FreeCAD errors:", result.stderr)
            
    except subprocess.CalledProcessError as e:
        error_msg = f'FreeCAD conversion failed with exit code {e.returncode}'
        if hasattr(e, 'stdout') and e.stdout:
            error_msg += f'\nStdout: {e.stdout}'
        if hasattr(e, 'stderr') and e.stderr:
            error_msg += f'\nStderr: {e.stderr}'
        print(f"FreeCAD subprocess error: {e}")
        print(f"Return code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        raise HTTPException(status_code=500, detail=error_msg)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail='FreeCAD conversion timed out')

    if not step_path.exists():
        raise HTTPException(status_code=500, detail='Conversion produced no output')
    
    # Step 3: Compress the STEP file
    zip_path = job_dir / 'output.zip'
    try:
        print(f"Compressing {step_path.stat().st_size} byte STEP file...")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
            zipf.write(step_path, 'converted.step')
        
        # Check compression ratio
        original_size = step_path.stat().st_size
        compressed_size = zip_path.stat().st_size
        compression_ratio = (1 - compressed_size / original_size) * 100
        
        print(f"Compression: {original_size:,} → {compressed_size:,} bytes ({compression_ratio:.1f}% reduction)")
        
    except Exception as e:
        print(f"Compression failed: {e}")
        # Fall back to uncompressed file
        return FileResponse(path=str(step_path), filename='converted.step', media_type='application/octet-stream')
    
    return FileResponse(path=str(zip_path), filename='converted.zip', media_type='application/zip')
