# This script converts OBJ to STEP using FreeCAD and expects two args: input_obj, output_step
import sys
import os
from pathlib import Path

try:
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    # Validate input file exists
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist")
        sys.exit(1)
    
    # Import FreeCAD modules
    try:
        import FreeCAD
        import Mesh
        import Part
    except ImportError as e:
        print(f"Error importing FreeCAD modules: {e}")
        sys.exit(1)
    
    # Create a new document
    doc = FreeCAD.newDocument()
    
    try:
        # Load mesh from OBJ file
        mesh = Mesh.Mesh(str(input_path))
        
        # Check if mesh is valid
        if mesh.CountFacets == 0:
            print("Error: No mesh data found in input file")
            sys.exit(1)
        
        # Convert mesh to shape (may lose CAD topology; this is a best-effort)
        shape = Part.makeShapeFromMesh(mesh.Topology, 0.05)
        
        # Create a compound/part and export
        part = Part.makeCompound([shape])
        Part.export([part], str(output_path))
        
        # Verify output file was created
        if not output_path.exists():
            print("Error: Output file was not created")
            sys.exit(1)
        
        print(f'Successfully exported {output_path}')
        
    except Exception as e:
        print(f"Error during conversion: {e}")
        sys.exit(1)
    
    finally:
        # Clean up document
        FreeCAD.closeDocument(doc.Name)

except Exception as e:
    print(f"Script error: {e}")
    sys.exit(1)