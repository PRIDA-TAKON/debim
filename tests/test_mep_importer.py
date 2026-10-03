"""
Unit tests for MEP distribution & generic proxy element extraction and re-compilation.
"""

from pathlib import Path
import sys
import pytest
import ifcopenshell
import ifcopenshell.api

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debim.importer import import_ifc_to_manifest
from debim.compiler import compile_to_ifc, derive_custom_ifc_class
from debim.schema import IfcCustomElement
from tools.compare_ifc import count_ifc_elements


def test_legacy_schema_unsupported(tmp_path: Path):
    """Verify that unsupported legacy IFC schemas raise a clean ValueError."""
    ifc_file = ifcopenshell.file(schema="IFC2X3")
    test_ifc_path = tmp_path / "legacy.ifc"
    ifc_file.write(str(test_ifc_path))

    # Replace schema string in raw IFC STEP file
    content = test_ifc_path.read_text(encoding="utf-8")
    legacy_content = content.replace("FILE_SCHEMA(('IFC2X3'));", "FILE_SCHEMA(('IFC2X_FINAL'));")
    test_ifc_path.write_text(legacy_content, encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported legacy IFC schema 'IFC2X_FINAL'"):
        import_ifc_to_manifest(test_ifc_path)


def test_derive_custom_ifc_class_mep_and_proxies():
    """Verify derive_custom_ifc_class correctly maps layer keywords to IFC entity classes."""
    assert derive_custom_ifc_class("architecture/proxies") == "IfcBuildingElementProxy"
    assert derive_custom_ifc_class("architecture/chimneys") == "IfcChimney"
    assert derive_custom_ifc_class("structure/accessories") == "IfcDiscreteAccessory"
    assert derive_custom_ifc_class("mep/ducts") == "IfcDuctSegment"
    assert derive_custom_ifc_class("mep/pipes") == "IfcPipeSegment"
    assert derive_custom_ifc_class("mep/terminals") == "IfcAirTerminal"
    assert derive_custom_ifc_class("mep/fittings") == "IfcFlowFitting"
    assert derive_custom_ifc_class("mep/valves") == "IfcValve"
    assert derive_custom_ifc_class("mep/dampers") == "IfcDamper"
    assert derive_custom_ifc_class("mep/flow_controllers") == "IfcFlowController"
    assert derive_custom_ifc_class("mep/controls") == "IfcDistributionControlElement"


def test_mep_flow_controls_extraction_and_recompilation(tmp_path: Path):
    """Test extraction, 3D box impostor dimensions, placement, and re-compilation of valves, dampers, and controls."""
    from debim.resolver import resolve_manifest
    from tools.render_visual_regression import extract_all_resolved_meshes

    model = ifcopenshell.file(schema="IFC4")
    proj = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Flow Control Test")
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    bldg = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Bldg")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level 1")

    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=proj)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[bldg], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=bldg)

    # Create flow control test elements
    valve = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcValve", name="GateValve-01")
    damper = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDamper", name="SmokeDamper-01")
    flow_ctrl = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcFlowController", name="FlowController-01")
    ctrl_elem = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDistributionControlElement", name="Thermostat-01")

    elems = [valve, damper, flow_ctrl, ctrl_elem]
    ifcopenshell.api.run("spatial.assign_container", model, products=elems, relating_structure=storey)

    orig_ifc_path = tmp_path / "orig_flow_controls.ifc"
    model.write(str(orig_ifc_path))

    # 1. Import to manifest
    manifest = import_ifc_to_manifest(orig_ifc_path)
    assert len(manifest.elements) == 4

    layers = [e.layer for e in manifest.elements if isinstance(e, IfcCustomElement)]
    assert "mep/valves" in layers
    assert "mep/dampers" in layers
    assert "mep/flow_controllers" in layers
    assert "mep/controls" in layers

    # 2. Verify all extracted elements have valid non-zero dimensions & placements
    for elem in manifest.elements:
        assert isinstance(elem, IfcCustomElement)
        assert elem.placement is not None
        assert elem.placement.position is not None
        assert elem.dimensions is not None
        assert elem.dimensions.width > 0
        assert elem.dimensions.height > 0
        if elem.dimensions.depth is not None:
            assert elem.dimensions.depth > 0

    # 3. Verify 3D box mesh resolution for visual regression
    resolved = resolve_manifest(manifest)
    meshes = extract_all_resolved_meshes(resolved)
    for elem in manifest.elements:
        assert elem.tag in meshes
        verts, faces = meshes[elem.tag]
        assert len(verts) > 0
        assert len(faces) > 0

    # 4. Re-compile to IFC
    recomp_ifc_path = tmp_path / "recomp_flow_controls.ifc"
    compile_to_ifc(manifest, recomp_ifc_path)

    orig_count, _ = count_ifc_elements(orig_ifc_path)
    recomp_count, recomp_breakdown = count_ifc_elements(recomp_ifc_path)

    assert orig_count == 4
    assert recomp_count == 4
    assert recomp_breakdown["IfcValve"] == 1
    assert recomp_breakdown["IfcDamper"] == 1
    assert recomp_breakdown["IfcFlowController"] == 1
    assert recomp_breakdown["IfcDistributionControlElement"] == 1


def test_mep_and_proxy_extraction_and_recompilation(tmp_path: Path):
    """Test creation, extraction, and re-compilation of MEP and proxy elements."""
    model = ifcopenshell.file(schema="IFC4")
    proj = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="MEP Test")
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    bldg = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Bldg")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level 1")

    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=proj)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[bldg], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=bldg)

    # Create test elements
    duct = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDuctSegment", name="Duct-01")
    term = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcAirTerminal", name="Diffuser-01")
    fit = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcFlowFitting", name="Elbow-01")
    proxy = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingElementProxy", name="Proxy-01")
    chimney = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcChimney", name="Chimney-01")
    acc = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDiscreteAccessory", name="Shoe-01")

    elems = [duct, term, fit, proxy, chimney, acc]
    ifcopenshell.api.run("spatial.assign_container", model, products=elems, relating_structure=storey)

    orig_ifc_path = tmp_path / "orig_mep.ifc"
    model.write(str(orig_ifc_path))

    # 1. Import to manifest
    manifest = import_ifc_to_manifest(orig_ifc_path)
    assert len(manifest.elements) == 6

    layers = [e.layer for e in manifest.elements if isinstance(e, IfcCustomElement)]
    assert "mep/ducts" in layers
    assert "mep/terminals" in layers
    assert "mep/fittings" in layers
    assert "architecture/proxies" in layers
    assert "architecture/chimneys" in layers
    assert "structure/accessories" in layers

    # 2. Re-compile to IFC
    recomp_ifc_path = tmp_path / "recomp_mep.ifc"
    compile_to_ifc(manifest, recomp_ifc_path)

    orig_count, orig_breakdown = count_ifc_elements(orig_ifc_path)
    recomp_count, recomp_breakdown = count_ifc_elements(recomp_ifc_path)

    assert orig_count == 6
    assert recomp_count == 6
    assert recomp_breakdown["IfcDuctSegment"] == 1
    assert recomp_breakdown["IfcAirTerminal"] == 1
    assert recomp_breakdown["IfcFlowFitting"] == 1
    assert recomp_breakdown["IfcBuildingElementProxy"] == 1
    assert recomp_breakdown["IfcChimney"] == 1
    assert recomp_breakdown["IfcDiscreteAccessory"] == 1


def test_port_aligned_fitting_placement(tmp_path: Path):
    """Verify that pipe and duct fitting placements align with connected port centerline junctions or fall back to centroid."""
    from debim.resolver import resolve_manifest

    model = ifcopenshell.file(schema="IFC4")
    proj = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Port Alignment Test")
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    bldg = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="Bldg")
    storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey", name="Level 1")

    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=proj)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[bldg], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[storey], relating_object=bldg)

    # 1. Elbow Fitting (IfcPipeFitting) with raw local placement at Port 1 face (1.0, 0.0, 0.0)
    elbow = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcPipeFitting", name="Elbow-90")
    pt_e = model.create_entity("IfcCartesianPoint", Coordinates=(1.0, 0.0, 0.0))
    axis_e = model.create_entity("IfcAxis2Placement3D", Location=pt_e)
    elbow.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=axis_e)

    pt_p1 = model.create_entity("IfcCartesianPoint", Coordinates=(1.0, 0.0, 0.0))
    dir_p1_z = model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    dir_p1_x = model.create_entity("IfcDirection", DirectionRatios=(0.0, 1.0, 0.0))
    axis_p1 = model.create_entity("IfcAxis2Placement3D", Location=pt_p1, Axis=dir_p1_z, RefDirection=dir_p1_x)
    port1 = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), Name="Port1")
    port1.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=axis_p1)

    pt_p2 = model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 1.0, 0.0))
    dir_p2_z = model.create_entity("IfcDirection", DirectionRatios=(0.0, 1.0, 0.0))
    dir_p2_x = model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    axis_p2 = model.create_entity("IfcAxis2Placement3D", Location=pt_p2, Axis=dir_p2_z, RefDirection=dir_p2_x)
    port2 = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), Name="Port2")
    port2.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=axis_p2)

    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=port1, RelatedElement=elbow)
    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=port2, RelatedElement=elbow)

    # 2. Tee Fitting (IfcDuctFitting) with 3 ports
    tee = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDuctFitting", name="Tee-Branch")
    pt_t = model.create_entity("IfcCartesianPoint", Coordinates=(-1.0, 0.0, 0.0))
    axis_t = model.create_entity("IfcAxis2Placement3D", Location=pt_t)
    tee.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=axis_t)

    t_p1 = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), Name="TeePort1")
    t_pt1 = model.create_entity("IfcCartesianPoint", Coordinates=(-1.0, 0.0, 0.0))
    t_axis1 = model.create_entity("IfcAxis2Placement3D", Location=t_pt1, Axis=model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0)), RefDirection=model.create_entity("IfcDirection", DirectionRatios=(0.0, 1.0, 0.0)))
    t_p1.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=t_axis1)

    t_p2 = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), Name="TeePort2")
    t_pt2 = model.create_entity("IfcCartesianPoint", Coordinates=(1.0, 0.0, 0.0))
    t_axis2 = model.create_entity("IfcAxis2Placement3D", Location=t_pt2, Axis=model.create_entity("IfcDirection", DirectionRatios=(-1.0, 0.0, 0.0)), RefDirection=model.create_entity("IfcDirection", DirectionRatios=(0.0, 1.0, 0.0)))
    t_p2.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=t_axis2)

    t_p3 = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), Name="TeePort3")
    t_pt3 = model.create_entity("IfcCartesianPoint", Coordinates=(0.0, 1.0, 0.0))
    t_axis3 = model.create_entity("IfcAxis2Placement3D", Location=t_pt3, Axis=model.create_entity("IfcDirection", DirectionRatios=(0.0, -1.0, 0.0)), RefDirection=model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0)))
    t_p3.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=t_axis3)

    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=t_p1, RelatedElement=tee)
    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=t_p2, RelatedElement=tee)
    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=t_p3, RelatedElement=tee)

    # 3. Parallel Coupling Fitting (IfcPipeFitting) with 2 collinear ports
    coupling = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcPipeFitting", name="Coupling-Straight")
    c_p1 = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), Name="CoupPort1")
    c_pt1 = model.create_entity("IfcCartesianPoint", Coordinates=(-0.5, 0.0, 0.0))
    c_axis1 = model.create_entity("IfcAxis2Placement3D", Location=c_pt1, Axis=model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0)), RefDirection=model.create_entity("IfcDirection", DirectionRatios=(0.0, 1.0, 0.0)))
    c_p1.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=c_axis1)

    c_p2 = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), Name="CoupPort2")
    c_pt2 = model.create_entity("IfcCartesianPoint", Coordinates=(0.5, 0.0, 0.0))
    c_axis2 = model.create_entity("IfcAxis2Placement3D", Location=c_pt2, Axis=model.create_entity("IfcDirection", DirectionRatios=(-1.0, 0.0, 0.0)), RefDirection=model.create_entity("IfcDirection", DirectionRatios=(0.0, 1.0, 0.0)))
    c_p2.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=c_axis2)

    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=c_p1, RelatedElement=coupling)
    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=c_p2, RelatedElement=coupling)

    # 4. Unlinked Fitting (0 ports)
    unlinked = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcPipeFitting", name="Unlinked-Fitting")
    u_pt = model.create_entity("IfcCartesianPoint", Coordinates=(5.0, 5.0, 0.0))
    u_axis = model.create_entity("IfcAxis2Placement3D", Location=u_pt)
    unlinked.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=u_axis)

    elems = [elbow, tee, coupling, unlinked]
    ifcopenshell.api.run("spatial.assign_container", model, products=elems, relating_structure=storey)

    ifc_path = tmp_path / "port_alignment_test.ifc"
    model.write(str(ifc_path))

    manifest = import_ifc_to_manifest(ifc_path)
    resolved = resolve_manifest(manifest)

    # Verify positions
    resolved_by_tag = {r.tag: r for r in resolved.custom_elements}

    # Elbow should be aligned to (0.0, 0.0, 0.0) centerline junction
    elbow_res = resolved_by_tag["Elbow-90"]
    assert pytest.approx(elbow_res.position[0], abs=1e-2) == 0.0
    assert pytest.approx(elbow_res.position[1], abs=1e-2) == 0.0
    assert pytest.approx(elbow_res.position[2], abs=1e-2) == 0.0

    # Tee should be aligned to (0.0, 0.0, 0.0) junction
    tee_res = resolved_by_tag["Tee-Branch"]
    assert pytest.approx(tee_res.position[0], abs=1e-2) == 0.0
    assert pytest.approx(tee_res.position[1], abs=1e-2) == 0.0
    assert pytest.approx(tee_res.position[2], abs=1e-2) == 0.0

    # Straight Coupling should be centered at midpoint (0.0, 0.0, 0.0)
    coup_res = resolved_by_tag["Coupling-Straight"]
    assert pytest.approx(coup_res.position[0], abs=1e-2) == 0.0
    assert pytest.approx(coup_res.position[1], abs=1e-2) == 0.0

    # Unlinked fitting should fall back to its placement location (5.0, 5.0, 0.0)
    unlinked_res = resolved_by_tag["Unlinked-Fitting"]
    assert pytest.approx(unlinked_res.position[0], abs=1e-2) == 5.0
    assert pytest.approx(unlinked_res.position[1], abs=1e-2) == 5.0
