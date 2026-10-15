from debim.compliance import check_topological_continuity, verify_structural_topology
from debim.schema import ProjectManifest


def create_base_manifest_dict():
    return {
        "schema": "IFC4-Minimal",
        "project": {"id": "PROJ-1", "name": "Cantilever Test Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "FL1", "name": "First Floor", "elevation": 0.0, "height": 3.5},
                {"id": "FL2", "name": "Second Floor", "elevation": 3.5, "height": 3.5},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0, "4": 10.0},
            "axes_y": {"A": 0.0, "B": 4.0, "C": 8.0},
        },
        "materials": [
            {"id": "CONCRETE", "name": "Concrete C25", "category": "CONCRETE", "unit_cost_ref": "MAT-C25"},
        ],
        "elements": [
            {
                "class": "IfcColumn",
                "tag": "C1",
                "material": "CONCRETE",
                "profile": {"shape": "BOX", "width": 0.3, "depth": 0.3},
                "placement": {"grid": ["1", "A"], "base_storey": "FL1", "top_storey": "FL2"},
            },
            {
                "class": "IfcColumn",
                "tag": "C2",
                "material": "CONCRETE",
                "profile": {"shape": "BOX", "width": 0.3, "depth": 0.3},
                "placement": {"grid": ["2", "A"], "base_storey": "FL1", "top_storey": "FL2"},
            },
        ],
    }


def test_standard_beam_between_columns():
    data = create_base_manifest_dict()
    data["elements"].append({
        "class": "IfcBeam",
        "tag": "B1",
        "material": "CONCRETE",
        "profile": {"shape": "BOX", "width": 0.2, "depth": 0.4},
        "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "FL2"},
    })
    manifest = ProjectManifest.model_validate(data)

    warnings = check_topological_continuity(manifest)
    assert len(warnings) == 0


def test_soil_bearing_ground_beam():
    data = create_base_manifest_dict()
    # Ground beam extending to grid 3 where no column exists, but support_type is SOIL_BEARING
    data["elements"].append({
        "class": "IfcBeam",
        "tag": "GB1",
        "material": "CONCRETE",
        "profile": {"shape": "BOX", "width": 0.2, "depth": 0.4},
        "placement": {
            "from_grid": ["1", "A"],
            "to_grid": ["3", "A"],
            "storey": "FL1",
            "support_type": "SOIL_BEARING",
        },
    })
    manifest = ProjectManifest.model_validate(data)

    warnings = verify_structural_topology(manifest)
    dangling_warnings = [w for w in warnings if w["type"] == "DANGLING_CANTILEVER"]
    assert len(dangling_warnings) == 0


def test_allow_cantilever_beam():
    data = create_base_manifest_dict()
    # Beam extending from C2 (grid 2, A) to grid 3, A (overhang cantilever)
    data["elements"].append({
        "class": "IfcBeam",
        "tag": "B-CANT-1",
        "material": "CONCRETE",
        "profile": {"shape": "BOX", "width": 0.2, "depth": 0.4},
        "placement": {
            "from_grid": ["2", "A"],
            "to_grid": ["3", "A"],
            "storey": "FL2",
            "allow_cantilever": True,
            "cantilever_end": "END",
        },
    })
    manifest = ProjectManifest.model_validate(data)

    warnings = check_topological_continuity(manifest)
    dangling_warnings = [w for w in warnings if w["type"] == "DANGLING_CANTILEVER"]
    assert len(dangling_warnings) == 0


def test_support_type_cantilever_beam():
    data = create_base_manifest_dict()
    data["elements"].append({
        "class": "IfcBeam",
        "tag": "B-CANT-2",
        "material": "CONCRETE",
        "profile": {"shape": "BOX", "width": 0.2, "depth": 0.4},
        "placement": {
            "from_grid": ["2", "A"],
            "to_grid": ["3", "A"],
            "storey": "FL2",
            "support_type": "CANTILEVER",
        },
    })
    manifest = ProjectManifest.model_validate(data)

    warnings = check_topological_continuity(manifest)
    dangling_warnings = [w for w in warnings if w["type"] == "DANGLING_CANTILEVER"]
    assert len(dangling_warnings) == 0


def test_unintended_dangling_beam_emits_warning():
    data = create_base_manifest_dict()
    # Beam extending from C2 (grid 2, A) to grid 3, A with no cantilever flags
    data["elements"].append({
        "class": "IfcBeam",
        "tag": "B-DANGLING",
        "material": "CONCRETE",
        "profile": {"shape": "BOX", "width": 0.2, "depth": 0.4},
        "placement": {
            "from_grid": ["2", "A"],
            "to_grid": ["3", "A"],
            "storey": "FL2",
        },
    })
    manifest = ProjectManifest.model_validate(data)

    warnings = check_topological_continuity(manifest)
    dangling_warnings = [w for w in warnings if w["type"] == "DANGLING_CANTILEVER"]
    assert len(dangling_warnings) == 1
    assert dangling_warnings[0]["tag"] == "B-DANGLING"


def test_fully_unsupported_beam_emits_warning():
    data = create_base_manifest_dict()
    # Beam in mid-air at grid 3,B to 4,B where no columns or supports exist
    data["elements"].append({
        "class": "IfcBeam",
        "tag": "B-FLOATING",
        "material": "CONCRETE",
        "profile": {"shape": "BOX", "width": 0.2, "depth": 0.4},
        "placement": {
            "from_grid": ["3", "B"],
            "to_grid": ["4", "B"],
            "storey": "FL2",
            "allow_cantilever": True,
        },
    })
    manifest = ProjectManifest.model_validate(data)

    warnings = check_topological_continuity(manifest)
    unsupported_warnings = [w for w in warnings if w["type"] == "UNSUPPORTED_BEAM"]
    assert len(unsupported_warnings) == 1
    assert unsupported_warnings[0]["tag"] == "B-FLOATING"
