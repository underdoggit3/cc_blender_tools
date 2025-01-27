# Copyright (C) 2021 Victor Soupday
# This file is part of CC/iC Blender Tools <https://github.com/soupday/cc_blender_tools>
#
# CC/iC Blender Tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# CC/iC Blender Tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with CC/iC Blender Tools.  If not, see <https://www.gnu.org/licenses/>.

import bpy, bmesh
import os, math, random
from mathutils import Vector
from . import geom, utils, jsonutils, bones, meshutils


HEAD_RIG_NAME = "RL_Hair_Rig_Head"
JAW_RIG_NAME = "RL_Hair_Rig_Jaw"
HAIR_BONE_PREFIX = "RL_Hair"
BEARD_BONE_PREFIX = "RL_Beard"
HEAD_BONE_NAMES = ["CC_Base_Head", "RL_Head", "Head", "head"]
JAW_BONE_NAMES = ["CC_Base_JawRoot", "RL_JawRoot", "JawRoot"]
EYE_BONE_NAMES = ["CC_Base_R_Eye", "CC_Base_L_Eye", "CC_Base_R_Eye", "CC_Base_L_Eye"]
ROOT_BONE_NAMES = ["CC_Base_Head", "RL_Head", "Head", "head", "CC_Base_JawRoot", "RL_JawRoot", "JawRoot"]
STROKE_JOIN_THRESHOLD = 1.0 / 100.0 # 1cm

def begin_hair_sculpt(chr_cache):
    return


def end_hair_sculpt(chr_cache):
    return


def find_obj_cache(chr_cache, obj):
    if chr_cache and obj and obj.type == "MESH":
        # try to find directly
        obj_cache = chr_cache.get_object_cache(obj)
        if obj_cache:
            return obj_cache
        # obj might be part of a split or a copy from original character object
        # so will have the same name but with duplication suffixes
        possible = []
        source_name = utils.strip_name(obj.name)
        for obj_cache in chr_cache.object_cache:
            if obj_cache.is_mesh() and obj_cache.source_name == source_name:
                possible.append(obj_cache)
        # if only one possibility return that
        if possible and len(possible) == 1:
            return possible[0]
        # try to find the correct object cache by matching the materials
        # try matching all the materials first
        for obj_cache in possible:
            o = obj_cache.get_object()
            if o:
                found = True
                for mat in obj.data.materials:
                    if mat not in o.data.materials:
                        found = False
                if found:
                    return obj_cache
        # then try just matching any
        for obj_cache in possible:
            o = obj_cache.get_object()
            if o:
                found = True
                for mat in obj.data.materials:
                    if mat in o.data.materials:
                        return obj_cache
    return None


def clear_particle_systems(obj):
    if utils.set_mode("OBJECT") and utils.set_only_active_object(obj):
        for i in range(0, len(obj.particle_systems)):
            bpy.ops.object.particle_system_remove()
        return True
    return False


def convert_hair_group_to_particle_systems(obj, curves):
    if clear_particle_systems(obj):
        for c in curves:
            if utils.set_only_active_object(c):
                bpy.ops.curves.convert_to_particle_system()


def export_blender_hair(op, chr_cache, objects, base_path):
    props = bpy.context.scene.CC3ImportProps
    prefs = bpy.context.preferences.addons[__name__.partition(".")[0]].preferences

    utils.expand_with_child_objects(objects)

    folder, name = os.path.split(base_path)
    file, ext = os.path.splitext(name)

    parents = []
    for obj in objects:
        if obj.type == "CURVES":
            if obj.parent:
                if obj.parent not in parents:
                    parents.append(obj.parent)
            else:
                op.report({'ERROR'}, f"Curve: {obj.data.name} has no parent!")

    json_data = { "Hair": { "Objects": { } } }
    export_id = 0

    for parent in parents:

        groups = {}

        obj_cache = find_obj_cache(chr_cache, parent)

        if obj_cache:

            parent_name = utils.determine_object_export_name(chr_cache, parent, obj_cache)

            json_data["Hair"]["Objects"][parent_name] = { "Groups": {} }

            if props.hair_export_group_by == "CURVE":
                for obj in objects:
                    if obj.type == "CURVES" and obj.parent == parent:
                        group = [obj]
                        name = obj.data.name
                        groups[name] = group
                        utils.log_info(f"Group: {name}, Object: {obj.data.name}")

            elif props.hair_export_group_by == "NAME":
                for obj in objects:
                    if obj.type == "CURVES" and obj.parent == parent:
                        name = utils.strip_name(obj.data.name)
                        if name not in groups.keys():
                            groups[name] = []
                        groups[name].append(obj)
                        utils.log_info(f"Group: {name}, Object: {obj.data.name}")

            else: #props.hair_export_group_by == "NONE":
                if "Hair" not in groups.keys():
                    groups["Hair"] = []
                for obj in objects:
                    if obj.type == "CURVES" and obj.parent == parent:
                        groups["Hair"].append(obj)
                        utils.log_info(f"Group: Hair, Object: {obj.data.name}")

            for group_name in groups.keys():
                file_name = f"{file}_{export_id}.abc"
                file_path = os.path.join(folder, file_name)
                export_id += 1

                convert_hair_group_to_particle_systems(parent, groups[group_name])

                utils.try_select_objects(groups[group_name], True)
                utils.set_active_object(parent)

                json_data["Hair"]["Objects"][parent_name]["Groups"][group_name] = { "File": file_name }

                bpy.ops.wm.alembic_export(
                        filepath=file_path,
                        check_existing=False,
                        global_scale=100.0,
                        start=1, end=1,
                        use_instancing = False,
                        selected=True,
                        visible_objects_only=True,
                        evaluation_mode = "RENDER",
                        packuv=False,
                        export_hair=True,
                        export_particles=True)

                clear_particle_systems(parent)

        else:
            op.report({'ERROR'}, f"Unable to find source mesh object in character for: {parent.name}!")

    new_json_path = os.path.join(folder, file + ".json")
    jsonutils.write_json(json_data, new_json_path)

    utils.try_select_objects(objects, True)


def create_curve():
    curve = bpy.data.curves.new("Hair Curve", type="CURVE")
    curve.dimensions = "3D"
    obj = bpy.data.objects.new("Hair Curve", curve)
    bpy.context.collection.objects.link(obj)
    return curve


def create_hair_curves():
    curves = bpy.data.hair_curves.new("Hair Curves")
    obj = bpy.data.objects.new("Hair Curves", curves)
    bpy.context.collection.objects.link(obj)
    return curves


def add_poly_spline(points, curve):
    """Create a poly curve from a list of Vectors
    """
    spline : bpy.types.Spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for i in range(0, len(points)):
        co = points[i]
        spline.points[i].co = (co.x, co.y, co.z, 1.0)


def parse_loop(bm, edge_index, edges_left, loop, edge_map):
    """Returns a set of vertex indices in the edge loop
    """
    if edge_index in edges_left:
        edges_left.remove(edge_index)
        edge = bm.edges[edge_index]
        loop.add(edge.verts[0].index)
        loop.add(edge.verts[1].index)
        if edge.index in edge_map:
            for ce in edge_map[edge.index]:
                parse_loop(bm, ce, edges_left, loop, edge_map)


def sort_func_u(vert_uv_pair):
    return vert_uv_pair[-1].x


def sort_func_v(vert_uv_pair):
    return vert_uv_pair[-1].y


def sort_verts_by_uv(obj, bm, loop, uv_map, dir):
    sorted = []
    for vert in loop:
        uv = uv_map[vert]
        sorted.append([vert, uv])
    if dir.x > 0:
        sorted.sort(reverse=False, key=sort_func_u)
    elif dir.x < 0:
        sorted.sort(reverse=True, key=sort_func_u)
    elif dir.y > 0:
        sorted.sort(reverse=False, key=sort_func_v)
    else:
        sorted.sort(reverse=True, key=sort_func_v)
    return [ obj.matrix_world @ bm.verts[v].co for v, uv in sorted]


def get_ordered_coordinate_loops(obj, bm, edges, dir, uv_map, edge_map):
    edges_left = set(edges)
    loops = []

    # separate edges into vertex loops
    while len(edges_left) > 0:
        loop = set()
        edge_index = list(edges_left)[0]
        parse_loop(bm, edge_index, edges_left, loop, edge_map)
        sorted = sort_verts_by_uv(obj, bm, loop, uv_map, dir)
        loops.append(sorted)

    return loops


def get_vert_loops(obj, bm, edges, edge_map):
    edges_left = set(edges)
    vert_loops = []

    # separate edges into vertex loops
    while len(edges_left) > 0:
        loop = set()
        edge_index = list(edges_left)[0]
        parse_loop(bm, edge_index, edges_left, loop, edge_map)
        verts = [ index for index in loop]
        vert_loops.append(verts)

    return vert_loops


def merge_length_coordinate_loops(loops):

    size = len(loops[0])

    for merged in loops:
        if len(merged) != size:
            return None

    num = len(loops)
    merged = []

    for i in range(0, size):
        co = Vector((0,0,0))
        for l in range(0, num):
            co += loops[l][i]
        co /= num
        merged.append(co)

    return merged


def sort_lateral_card(obj, bm, loops, uv_map, dir):

    sorted = []
    card = {}

    for loop in loops:
        co = Vector((0,0,0))
        uv = Vector((0,0))
        count = 0
        for vert_index in loop:
            co += obj.matrix_world @ bm.verts[vert_index].co
            uv += uv_map[vert_index]
            count += 1
        co /= count
        uv /= count
        sorted.append([co, loop, uv])

    if dir.x > 0:
        sorted.sort(reverse=False, key=sort_func_u)
    elif dir.x < 0:
        sorted.sort(reverse=True, key=sort_func_u)
    elif dir.y > 0:
        sorted.sort(reverse=False, key=sort_func_v)
    else:
        sorted.sort(reverse=True, key=sort_func_v)

    card["median"] = [ co for co, loop, uv in sorted ]
    card["loops"] = [ loop for co, loop, uv in sorted ]
    return card


def selected_cards_to_length_loops(chr_cache, obj, card_dir : Vector, one_loop_per_card = True):
    prefs = bpy.context.preferences.addons[__name__.partition(".")[0]].preferences
    props = bpy.context.scene.CC3ImportProps

    # normalize card dir
    card_dir.normalize()

    # select linked and set to edge mode
    utils.edit_mode_to(obj, only_this=True)
    bpy.ops.mesh.select_linked(delimit={'UV'})
    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')

    # object mode to save edit changes
    utils.object_mode_to(obj)

    deselect_invalid_materials(chr_cache, obj)

    # get the bmesh
    mesh = obj.data
    bm = geom.get_bmesh(mesh)

    # get lists of the faces in each selected island
    islands = geom.get_uv_islands(bm, 0, use_selected=True)

    utils.log_info(f"{len(islands)} islands selected.")

    all_loops = []

    for island in islands:

        utils.log_info(f"Processing island, faces: {len(island)}")
        utils.log_indent()

        # each island has a unique UV map
        uv_map = geom.get_uv_island_map(bm, 0, island)

        # get all edges aligned with the card dir in the island
        edges = geom.get_uv_aligned_edges(bm, island, card_dir, uv_map,
                                                    dir_threshold=props.hair_curve_dir_threshold)

        utils.log_info(f"{len(edges)} aligned edges.")

        # map connected edges
        edge_map = geom.get_linked_edge_map(bm, edges)

        # separate into ordered vertex loops
        loops = get_ordered_coordinate_loops(obj, bm, edges, card_dir, uv_map, edge_map)

        utils.log_info(f"{len(loops)} ordered loops.")

        # (merge and) generate poly curves
        if one_loop_per_card:
            loop = merge_length_coordinate_loops(loops)
            if loop:
                all_loops.append(loop)
            else:
                utils.log_info("Loops have differing lengths, skipping.")
        else:
            for loop in loops:
                all_loops.append(loop)

        utils.log_recess()

    #for face in bm.faces: face.select = False
    #for edge in bm.edges: edge.select = False
    #for vert in bm.verts: vert.select = False
    #for e in edges:
    #    bm.edges[e].select = True

    bm.to_mesh(mesh)

    return all_loops


def selected_cards_to_curves(chr_cache, obj, card_dir : Vector, one_loop_per_card = True):
    curve = create_curve()
    loops = selected_cards_to_length_loops(chr_cache, obj, card_dir, one_loop_per_card)
    for loop in loops:
        add_poly_spline(loop, curve)
    # TODO
    # Put the curve object to the same scale as the body mesh
    # With roots above the scalp plant the root of the curves into the scalp? (within tolerance)
    #   or add an new root point on the scalp...
    # With roots below the scalp, crop the loop
    # convert to curves
    # set curve render subdivision to at least 2
    # snap curves to surface


def loop_length(loop, index = -1):
    if index == -1:
        index = len(loop) - 1
    p0 = loop[0]
    d = 0
    for i in range(1, index + 1):
        p1 = loop[i]
        d += (p1 - p0).length
        p0 = p1
    return d


def eval_loop_at(loop, length, fac):
    p0 = loop[0]
    f0 = 0
    for i in range(1, len(loop)):
        p1 = loop[i]
        v = p1 - p0
        fl = v.length / length
        f1 = f0 + fl
        if fac <= f1 and fac >= f0:
            df = fac - f0
            return p0 + v * (df / fl)
        f0 = f1
        p0 = p1
        f1 += fl
    return p0


def is_on_loop(co, loop, threshold = 0.001):
    """Is the coordinate on the loop.
       (All coordintes should be in world space)"""
    p0 = loop[0]
    min_distance = threshold + 1.0
    for i in range(1, len(loop)):
        p1 = loop[i]
        dist, fac = distance_from_line(co, p0, p1)
        if dist < min_distance:
            min_distance = dist
        if min_distance < threshold:
            return True
        p0 = p1
    return min_distance < threshold


def clear_hair_bone_weights(chr_cache, arm, objects, bone_mode):
    utils.object_mode_to(arm)

    bone_chains = get_bone_chains(chr_cache, arm, bone_mode)

    hair_bones = []
    for bone_chain in bone_chains:
        for bone_def in bone_chain:
            hair_bones.append(bone_def["name"])

    for obj in objects:
        remove_hair_bone_weights(arm, obj, hair_bone_list=hair_bones)

    arm.data.pose_position = "POSE"
    utils.pose_mode_to(arm)


def remove_hair_bones(chr_cache, arm, objects, bone_mode):
    utils.object_mode_to(arm)

    hair_bones = []
    bone_chains = None

    if bone_mode == "SELECTED":
        # in selected bone mode, only remove the bones in the selected chains
        bone_chains = get_bone_chains(chr_cache, arm, bone_mode)
        for bone_chain in bone_chains:
            for bone_def in bone_chain:
                hair_bones.append(bone_def["name"])
    else:
        # otherwise remove all possible hair bones
        for bone in arm.data.bones:
            if is_hair_bone(bone.name) and not is_hair_rig_bone(bone.name):
                hair_bones.append(bone.name)

    # remove the bones in edit mode
    if hair_bones and utils.edit_mode_to(arm, True):
        for bone_name in hair_bones:
            arm.data.edit_bones.remove(arm.data.edit_bones[bone_name])

    # remove the hair rigs if there are no child bones left
    head_rig = get_hair_rig(chr_cache, arm, "HEAD")
    jaw_rig = get_hair_rig(chr_cache, arm, "JAW")
    if head_rig and not head_rig.children and utils.edit_mode_to(arm):
        arm.data.edit_bones.remove(head_rig)
    if jaw_rig and not jaw_rig.children and utils.edit_mode_to(arm):
        arm.data.edit_bones.remove(jaw_rig)

    #if no objects selected, use all mesh objects in the character
    if not objects:
        objects = chr_cache.get_all_objects(include_children = True, of_type = "MESH")

    #remove the weights from the character meshes
    for obj in objects:
        remove_hair_bone_weights(arm, obj, hair_bone_list=hair_bones)

    utils.object_mode_to(arm)


def contains_hair_bone_chain(arm, loop_index, prefix):
    """Edit mode"""
    for bone in arm.data.edit_bones:
        if bone.name.startswith(f"{prefix}_{loop_index}_"):
            return True
    return False


def find_unused_hair_bone_index(arm, loop_index, prefix):
    """Edit mode"""
    while contains_hair_bone_chain(arm, loop_index, prefix):
        loop_index += 1
    return loop_index


def get_hair_rig(chr_cache, arm, parent_mode, create_if_missing = False):
    root_bone_name = get_root_bone_name(chr_cache, arm, parent_mode)
    if parent_mode == "JAW":
        hair_rig_name = JAW_RIG_NAME
    else:
        hair_rig_name = HEAD_RIG_NAME
    hair_rig = bones.get_edit_bone(arm, hair_rig_name)
    if not hair_rig and create_if_missing:
        head_center_position = get_hair_rig_position(chr_cache, arm, parent_mode)
        hair_rig = bones.new_edit_bone(arm, hair_rig_name, root_bone_name)
        hair_rig.head = arm.matrix_world.inverted() @ head_center_position
        hair_rig.tail = arm.matrix_world.inverted() @ (head_center_position + Vector((0,1/32,0)))
        hair_rig.align_roll(Vector((0,0,1)))
        bones.set_edit_bone_layer(arm, hair_rig_name, 24)
    return hair_rig


def is_nearby_bone(arm, world_pos):
    """Edit mode"""
    for edit_bone in arm.data.edit_bones:
        length = (world_pos - arm.matrix_world @ edit_bone.head).length
        print(length)
        if length < 0.01:
            return True
    return False


def custom_bone(chr_cache, arm, parent_mode, loop_index, bone_length, new_bones):
    hair_rig = get_hair_rig(chr_cache, arm, parent_mode, create_if_missing=True)

    hair_bone_prefix = get_hair_bone_prefix(parent_mode)

    if hair_rig:

        parent_bone = hair_rig

        bone_name = f"{hair_bone_prefix}_{loop_index}_0"
        bone : bpy.types.EditBone = bones.new_edit_bone(arm, bone_name, parent_bone.name)
        new_bones.append(bone_name)
        bone.select = True
        bone.select_head = True
        bone.select_tail = True
        world_origin = arm.matrix_world @ hair_rig.head
        world_pos = world_origin + Vector((0, 0.05, 0.15))
        while is_nearby_bone(arm, world_pos):
            world_pos += Vector((0, 0.0175, 0))
        world_head = world_pos
        world_tail = world_pos + Vector((0, 0, bone_length))
        bone.head = arm.matrix_world.inverted() @ world_head
        bone.tail = arm.matrix_world.inverted() @ world_tail
        bone_z = (((world_head + world_tail) * 0.5) - world_origin).normalized()
        bone.align_roll(bone_z)
        # set bone layer to 25, so we can show only the added hair bones 'in front'
        bones.set_edit_bone_layer(arm, bone_name, 25)
        # don't directly connect first bone in a chain
        bone.use_connect = False
        return True

    return False


def get_linked_bones(edit_bone, bone_list):
    if edit_bone.name not in bone_list:
        bone_list.append(edit_bone.name)
        for child_bone in edit_bone.children:
            get_linked_bones(child_bone, bone_list)
    return bone_list


def bone_chains_match(arm, bone_list_a, bone_list_b, tolerance = 0.001):

    tolerance /= ((arm.scale[0] + arm.scale[1] + arm.scale[2]) / 3.0)

    for bone_name_a in bone_list_a:
        edit_bone_a = arm.data.edit_bones[bone_name_a]
        has_match = False
        for bone_name_b in bone_list_b:
            edit_bone_b = arm.data.edit_bones[bone_name_b]
            delta = (edit_bone_a.head - edit_bone_b.head).length + (edit_bone_a.tail - edit_bone_b.tail).length
            if (delta < tolerance):
                has_match = True
        if not has_match:
            return False
    return True


def bone_chain_matches_loop(arm, bone_list, loop, threshold = 0.001):
    for bone_name in bone_list:
        if bone_name in arm.data.edit_bones:
            edit_bone = arm.data.edit_bones[bone_name]
            if not is_on_loop(arm.matrix_world @ edit_bone.head, loop, threshold):
                return False
            if not is_on_loop(arm.matrix_world @ edit_bone.tail, loop, threshold):
                return False
        else:
            return False
    return True


def remove_existing_loop_bones(chr_cache, arm, loops):
    """Removes any bone chains in the hair rig that align with the loops"""

    props = bpy.context.scene.CC3ImportProps
    bone_selection_mode = props.hair_rig_bind_bone_mode

    if bone_selection_mode == "SELECTED":
        # select all linked bones
        utils.edit_mode_to(arm)
        bpy.ops.armature.select_linked()
        utils.object_mode_to(arm)

    utils.edit_mode_to(arm)

    head_rig = get_hair_rig(chr_cache, arm, "HEAD")
    jaw_rig = get_hair_rig(chr_cache, arm, "JAW")
    hair_rigs = [head_rig, jaw_rig]

    remove_bone_list = []
    remove_loop_list = []
    removed_roots = []

    for hair_rig in hair_rigs:
        if hair_rig:

            for chain_root in hair_rig.children:
                chain_root : bpy.types.EditBone
                if chain_root not in removed_roots:
                    chain_bones = get_linked_bones(chain_root, [])
                    for loop in loops:
                        if bone_chain_matches_loop(arm, chain_bones, loop, 0.001):
                            remove_bones = False
                            remove_loop = False
                            if bone_selection_mode == "SELECTED":
                                if chain_root.select:
                                    # if the chain is selected, then it is to be replaced, so remove it.
                                    remove_bones = True
                                else:
                                    # otherwise remove the loop, so it won't generate new bones over the existing bones.
                                    remove_loop = True
                            else:
                                remove_bones = True

                            if remove_bones:
                                utils.log_info(f"Existing bone chain starting: {chain_root.name} is to be re-generated.")
                                remove_bone_list.extend(chain_bones)
                                removed_roots.append(chain_root)
                            if remove_loop:
                                utils.log_info(f"Existing bone chain starting: {chain_root.name} will not be replaced.")
                                remove_loop_list.append(loop)

        if remove_bone_list:
            for bone_name in remove_bone_list:
                if bone_name in arm.data.edit_bones:
                    utils.log_info(f"Removing bone on generating loop: {bone_name}")
                    arm.data.edit_bones.remove(arm.data.edit_bones[bone_name])
                else:
                    utils.log_info(f"Already deleted: {bone_name} ?")

        if remove_loop_list:
            for loop in remove_loop_list:
                if loop in loops:
                    loops.remove(loop)
                    utils.log_info(f"Removing loop from generation list")

    return


def remove_duplicate_bones(chr_cache, arm):
    """Remove any duplicate bone chains"""

    head_rig = get_hair_rig(chr_cache, arm, "HEAD")
    jaw_rig = get_hair_rig(chr_cache, arm, "JAW")
    hair_rigs = [head_rig, jaw_rig]

    remove_list = []
    removed_roots = []

    utils.edit_mode_to(arm)

    for hair_rig in hair_rigs:

        if hair_rig:

            for chain_root in hair_rig.children:
                if chain_root not in removed_roots:
                    chain_bones = get_linked_bones(chain_root, [])
                    for i in range(len(hair_rig.children)-1, 0, -1):
                        test_chain_root = hair_rig.children[i]
                        if test_chain_root not in removed_roots:
                            test_chain_bones = get_linked_bones(test_chain_root, [])
                            if chain_root == test_chain_root:
                                break
                            if bone_chains_match(arm, test_chain_bones, chain_bones, 0.001):
                                remove_list.extend(test_chain_bones)
                                removed_roots.append(test_chain_root)

    if remove_list:
        for bone_name in remove_list:
            if bone_name in arm.data.edit_bones:
                utils.log_info(f"Removing duplicate bone: {bone_name}")
                arm.data.edit_bones.remove(arm.data.edit_bones[bone_name])
            else:
                utils.log_info(f"Already deleted: {bone_name} ?")

    # object mode to save changes to edit bones
    utils.object_mode_to(arm)

    return


def loop_to_bones(chr_cache, arm, parent_mode, loop, loop_index, bone_length, skip_length, new_bones):
    """Generate hair rig bones from vertex loops. Must be in edit mode on armature."""

    if len(loop) < 2:
        return False

    length = loop_length(loop)

    # maximum skip length of 3/4 length
    skip_length = min(skip_length, 3.0 * length / 4.0)
    segments = max(1, round((length - skip_length) / bone_length))

    fac = skip_length / length
    df = (1.0 - fac) / segments
    chain = []
    first = True

    hair_rig = get_hair_rig(chr_cache, arm, parent_mode, create_if_missing=True)

    hair_bone_prefix = get_hair_bone_prefix(parent_mode)

    if hair_rig:

        parent_bone = hair_rig

        for s in range(0, segments):
            bone_name = f"{hair_bone_prefix}_{loop_index}_{s}"
            bone : bpy.types.EditBone = bones.new_edit_bone(arm, bone_name, parent_bone.name)
            new_bones.append(bone_name)
            bone.select = True
            bone.select_head = True
            bone.select_tail = True
            world_head = eval_loop_at(loop, length, fac)
            world_tail = eval_loop_at(loop, length, fac + df)
            bone.head = arm.matrix_world.inverted() @ world_head
            bone.tail = arm.matrix_world.inverted() @ world_tail
            world_origin = arm.matrix_world @ hair_rig.head
            bone_z = (((world_head + world_tail) * 0.5) - world_origin).normalized()
            bone.align_roll(bone_z)
            parent_bone = bone
            # set bone layer to 25, so we can show only the added hair bones 'in front'
            bones.set_edit_bone_layer(arm, bone_name, 25)
            chain.append(bone_name)
            if first:
                bone.use_connect = False
                first = False
            else:
                bone.use_connect = True
            fac += df

        return True

    return False


def get_root_edit_bone(chr_cache, arm, parent_mode):
    try:
        return arm.data.edit_bones[get_root_bone_name(chr_cache, arm, parent_mode)]
    except:
        return None


def get_root_bone_name(chr_cache, arm, parent_mode):
    if parent_mode == "HEAD":
        possible_head_bones = HEAD_BONE_NAMES
        for name in possible_head_bones:
            if name in arm.data.bones:
                return name
        return None
    elif parent_mode == "JAW":
        possible_jaw_bones = JAW_BONE_NAMES
        for name in possible_jaw_bones:
            if name in arm.data.bones:
                return name
        return None


def get_hair_bone_prefix(parent_mode):
    return BEARD_BONE_PREFIX if parent_mode == "JAW" else HAIR_BONE_PREFIX


def is_hair_bone(bone_name):
    if bone_name.startswith(HAIR_BONE_PREFIX) or bone_name.startswith(BEARD_BONE_PREFIX):
        return True
    else:
        return False


def is_hair_rig_bone(bone_name):
    if bone_name.startswith(HEAD_RIG_NAME) or bone_name.startswith(JAW_RIG_NAME):
        return True
    else:
        return False


def selected_cards_to_bones(chr_cache, arm, obj, parent_mode, card_dir : Vector,
                            one_loop_per_card = True, bone_length = 0.075, skip_length = 0.075):
    """Lengths in world space units (m)."""

    mode_selection = utils.store_mode_selection_state()
    arm_pose = reset_pose(arm)

    repair_orphaned_hair_bones(chr_cache, arm)

    bones.show_armature_layers(arm, [25], in_front=True)

    hair_bone_prefix = get_hair_bone_prefix(parent_mode)

    # check root bone exists...
    root_bone_name = get_root_bone_name(chr_cache, arm, parent_mode)
    root_bone = bones.get_pose_bone(arm, root_bone_name)
    if root_bone:
        loops = selected_cards_to_length_loops(chr_cache, obj, card_dir, one_loop_per_card)
        utils.edit_mode_to(arm)
        remove_existing_loop_bones(chr_cache, arm, loops)
        for edit_bone in arm.data.edit_bones:
            edit_bone.select_head = False
            edit_bone.select_tail = False
            edit_bone.select = False
        loop_index = 1
        new_bones = []
        for loop in loops:
            loop_index = find_unused_hair_bone_index(arm, loop_index, hair_bone_prefix)
            if loop_to_bones(chr_cache, arm, parent_mode, loop, loop_index, bone_length, skip_length, new_bones):
                loop_index += 1

    remove_duplicate_bones(chr_cache, arm)

    utils.object_mode_to(arm)

    restore_pose(arm, arm_pose)
    utils.restore_mode_selection_state(mode_selection)


def get_hair_cards_lateral(chr_cache, obj, card_dir : Vector, card_selection_mode):
    prefs = bpy.context.preferences.addons[__name__.partition(".")[0]].preferences
    props = bpy.context.scene.CC3ImportProps

    # normalize card dir
    card_dir.normalize()

    # select linked and set to edge mode
    utils.edit_mode_to(obj, only_this=True)
    if card_selection_mode == "ALL":
        bpy.ops.mesh.select_all(action='SELECT')
    else:
        bpy.ops.mesh.select_linked(delimit={'UV'})

    bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')

    # object mode to save edit changes
    utils.object_mode_to(obj)

    deselect_invalid_materials(chr_cache, obj)

    # get the bmesh
    mesh = obj.data
    bm = geom.get_bmesh(mesh)

    # get lists of the faces in each selected island
    islands = geom.get_uv_islands(bm, 0, use_selected=True)

    utils.log_info(f"{len(islands)} islands selected.")

    cards = []

    for island in islands:

        utils.log_info(f"Processing island, faces: {len(island)}")
        utils.log_indent()

        # each island has a unique UV map
        uv_map = geom.get_uv_island_map(bm, 0, island)

        # get all edges NOT aligned with the card dir in the island, i.e. the lateral edges
        edges = geom.get_uv_aligned_edges(bm, island, card_dir, uv_map,
                                          get_non_aligned=True, dir_threshold=props.hair_curve_dir_threshold)

        utils.log_info(f"{len(edges)} non-aligned edges.")

        # map connected edges
        edge_map = geom.get_linked_edge_map(bm, edges)

        # separate into lateral vertex loops
        vert_loops = get_vert_loops(obj, bm, edges, edge_map)

        utils.log_info(f"{len(vert_loops)} lateral loops.")

        # generate hair card info
        # a median coordinate loop representing the median positions of the hair card
        card = sort_lateral_card(obj, bm, vert_loops, uv_map, card_dir)
        cards.append(card)

        utils.log_recess()

    return bm, cards


def distance_from_line(co, start, end):
    """Returns the distance from the line and where along the line it is closest."""
    line = end - start
    dir = line.normalized()
    length = line.length
    from_start : Vector = co - start
    from_end : Vector = co - end
    if line.dot(from_start) <= 0:
        return (co - start).length, 0.0
    elif line.dot(from_end) >= 0:
        return (co - end).length, 1.0
    else:
        return (line.cross(from_start) / length).length, min(1.0, max(0.0, dir.dot(from_start) / length))


def get_distance_to_bone_def(bone_def, co : Vector):
    #bone_def = { "name": pose_bone.name, "head": head, "tail": tail, "line": line, "dir": dir }
    head : Vector = bone_def["head"]
    tail : Vector = bone_def["tail"]
    return distance_from_line(co, head, tail)


def get_closest_bone_def(bone_chain, co, max_radius):
    least_distance = max_radius * 2.0
    least_bone_def = bone_chain[0]
    least_fac = 0
    for bone_def in bone_chain:
        d, f = get_distance_to_bone_def(bone_def, co)
        if d < least_distance:
            least_distance = d
            least_bone_def = bone_def
            least_fac = f
    return least_bone_def, least_distance, least_fac


def get_weighted_bone_distance(bone_chain, max_radius, median_loop, median_length):
    weighted_distance = 0
    co_length = 0
    last_co = median_loop[0]
    for co in median_loop:
        co_length += (co - last_co).length
        factor = co_length / median_length
        bone_def, distance, fac = get_closest_bone_def(bone_chain, co, max_radius)
        weighted_distance += distance * factor * 2.0
    return weighted_distance / len(median_loop)


def weight_card_to_bones(obj, bm : bmesh.types.BMesh, card, sorted_bones, max_radius, max_bones, max_weight,
                         curve, variance):
    props = bpy.context.scene.CC3ImportProps
    CC4_SPRING_RIG = props.hair_rig_target == "CC4"

    # vertex weights are in the deform layer of the BMesh verts

    bm.verts.layers.deform.verify()
    dl = bm.verts.layers.deform.active

    median = card["median"]

    median_length = loop_length(median)

    if len(sorted_bones) < max_bones:
        max_bones = len(sorted_bones)

    min_weight = 0.01 if CC4_SPRING_RIG else 0.0

    bone_weight_variance_mods = []
    for i in range(0, max_bones):
        bone_weight_variance_mods.append(random.uniform(max_weight * (1 - variance), max_weight))

    first_bone_groups = []
    if CC4_SPRING_RIG:
        for b in range(0, max_bones):
            bone_chain = sorted_bones[b]["bones"]
            bone_def = bone_chain[0]
            bone_name = bone_def["name"]
            vg = meshutils.add_vertex_group(obj, bone_name)
            first_bone_groups.append(vg)

    for i, co in enumerate(median):
        ml = loop_length(median, i)
        card_length_fac = math.pow(ml / median_length, curve)
        for b in range(0, max_bones):
            bone_chain = sorted_bones[b]["bones"]
            bone_def, bone_distance, bone_fac = get_closest_bone_def(bone_chain, co, max_radius)

            weight_distance = min(max_radius, max(0, max_radius - bone_distance))
            weight = bone_weight_variance_mods[b] * (weight_distance / max_radius) / max_bones

            if CC4_SPRING_RIG:
                bone_fac = 1.0
            elif bone_def != bone_chain[0]:
                bone_fac = 1.0

            weight *= max(0, min(bone_fac, card_length_fac))
            weight = max(min_weight, weight)

            bone_name = bone_def["name"]
            vg = meshutils.add_vertex_group(obj, bone_name)
            if vg:
                vert_loop = card["loops"][i]
                for vert_index in vert_loop:
                    vertex = bm.verts[vert_index]
                    vertex[dl][vg.index] = weight
                    if CC4_SPRING_RIG:
                        first_vg = first_bone_groups[b]
                        vertex[dl][first_vg.index] = 1 - max_weight


def sort_func_weighted_distance(bone_weight_distance):
    return bone_weight_distance["distance"]


def assign_bones(obj, bm, cards, bone_chains, max_radius, max_bones, max_weight, curve, variance):
    for i, card in enumerate(cards):
        median = card["median"]
        median_length = loop_length(median)
        sorted_bones = []
        for bone_chain in bone_chains:
            weighted_distance = get_weighted_bone_distance(bone_chain, max_radius, median, median_length)
            #if weighted_distance < max_radius:
            bone_weight_distance = {"distance": weighted_distance, "bones": bone_chain}
            sorted_bones.append(bone_weight_distance)
        sorted_bones.sort(reverse=False, key=sort_func_weighted_distance)
        weight_card_to_bones(obj, bm, card, sorted_bones, max_radius, max_bones, max_weight, curve, variance)


def remove_hair_bone_weights(arm, obj : bpy.types.Object, scale_existing_weights = 1.0, hair_bone_list = None):
    """Remove vertex groups starting with 'RL_Hair/RL_Beard' for selected bones (or all bones if none selected)
    """

    utils.object_mode_to(obj)

    all_hair_groups = []
    for vg in obj.vertex_groups:
            if is_hair_bone(vg.name):
                all_hair_groups.append(vg.name)

    if not hair_bone_list:
        hair_bone_list = all_hair_groups

    vg : bpy.types.VertexGroup
    for vg in obj.vertex_groups:
        if vg.name not in all_hair_groups and scale_existing_weights <= 0.001:
            hair_bone_list.append(vg.name)

    for vg_name in hair_bone_list:
        meshutils.remove_vertex_group(obj, vg_name)

    utils.edit_mode_to(obj)
    utils.object_mode_to(obj)


def scale_existing_weights(obj, bm, scale):
    bm.verts.ensure_lookup_table()
    bm.verts.layers.deform.verify()
    dl = bm.verts.layers.deform.active
    for vert in bm.verts:
        for vg in obj.vertex_groups:
            if vg.index in vert[dl].keys():
                vert[dl][vg.index] *= scale


def get_hair_rig_position(chr_cache, arm, root_mode):
    """Returns the approximate position inside the head between the ears at nose height."""

    head_edit_bone = get_root_edit_bone(chr_cache, arm, "HEAD")

    if head_edit_bone:
        head_pos = arm.matrix_world @ head_edit_bone.head

        eye_pos = Vector((0,0,0))
        count = 0
        for eye_bone_name in EYE_BONE_NAMES:
            eye_edit_bone = bones.get_edit_bone(arm, eye_bone_name)
            if eye_edit_bone:
                count += 1
                eye_pos += arm.matrix_world @ eye_edit_bone.head

        if count > 0:
            eye_pos /= count

            if root_mode == "HEAD":
                return Vector((head_pos[0], head_pos[1], eye_pos[2]))
            elif root_mode == "JAW":
                return Vector((head_pos[0], (head_pos[1] + 2 * eye_pos[1]) / 3, head_pos[2]))
        else:
            return head_pos

    return None


def repair_orphaned_hair_bones(chr_cache, arm):

    utils.edit_mode_to(arm, True)

    head_rig = get_hair_rig(chr_cache, arm, "HEAD")
    jaw_rig = get_hair_rig(chr_cache, arm, "JAW")

    # find hair and beard bones and orphaned bones therein
    reparent_list = []
    bone_list = []
    for bone in arm.data.edit_bones:
        if head_rig and bone.name.startswith(HAIR_BONE_PREFIX) and bone != head_rig:
            bone_list.append([bone.name, head_rig])
            if not bone.parent:
                reparent_list.append([bone.name, head_rig])
            for child in bone.children:
                if not child.name.startswith(HAIR_BONE_PREFIX):
                    child.name = f"{HAIR_BONE_PREFIX}_{child.name}"
        elif jaw_rig and bone.name.startswith(BEARD_BONE_PREFIX) and bone != jaw_rig:
            bone_list.append([bone.name, jaw_rig])
            if not bone.parent:
                reparent_list.append([bone.name, jaw_rig])
            for child in bone.children:
                if not child.name.startswith(BEARD_BONE_PREFIX):
                    child.name = f"{BEARD_BONE_PREFIX}_{child.name}"

    # align bones roll z-axis away from rig bone
    if bone_list:
        for bone_pair in bone_list:
            bone_name = bone_pair[0]
            hair_rig = bone_pair[1]
            edit_bone = bones.get_edit_bone(arm, bone_name)
            if edit_bone:
                head = arm.matrix_world @ edit_bone.head
                tail = arm.matrix_world @ edit_bone.tail
                origin = arm.matrix_world @ hair_rig.head
                z_axis = (((head + tail) * 0.5) - origin).normalized()
                edit_bone.align_roll(z_axis)

    # reparent orphanded bones to root
    if reparent_list:
        for bone_pair in reparent_list:
            bone_name = bone_pair[0]
            hair_rig = bone_pair[1]
            arm.data.edit_bones[bone_name].parent = hair_rig

    # save edit mode changes
    utils.object_mode_to(arm)


def add_bone_chain(arm, edit_bone : bpy.types.EditBone, chain):

    if edit_bone.children and len(edit_bone.children) > 1:
        return False

    head = arm.matrix_world @ edit_bone.head
    tail = arm.matrix_world @ edit_bone.tail
    line = tail - head
    dir = line.normalized()

    # extend the last bone def in the chain to ensure full overlap with hair mesh
    if not edit_bone.children:
        line *= 4
        tail = head + line

    bone_def = { "name": edit_bone.name, "head": head, "tail": tail, "line": line, "dir": dir, "length": line.length }
    chain.append(bone_def)

    if edit_bone.children and len(edit_bone.children) == 1:
        return add_bone_chain(arm, edit_bone.children[0], chain)

    return True


def get_bone_chains(chr_cache, arm, bone_selection_mode):
    """Get each bone chain from the armature that contains the keyword HAIR_BONE_PREFIX, child of HEAD_BONE_NAME
    """

    repair_orphaned_hair_bones(chr_cache, arm)

    utils.edit_mode_to(arm)

    if bone_selection_mode == "SELECTED":
        # select all linked bones
        utils.edit_mode_to(arm)
        bpy.ops.armature.select_linked()
        utils.object_mode_to(arm)
        utils.edit_mode_to(arm)

    # NOTE: remember edit bones do not survive mode changes...
    bone_chains = []

    head_rig = get_hair_rig(chr_cache, arm, "HEAD")
    jaw_rig = get_hair_rig(chr_cache, arm, "JAW")
    hair_rigs = [head_rig, jaw_rig]

    for hair_rig in hair_rigs:
        if hair_rig:
            for child_bone in hair_rig.children:
                if child_bone.name.startswith(HAIR_BONE_PREFIX) or child_bone.name.startswith(BEARD_BONE_PREFIX):
                    if arm.data.bones[child_bone.name].select or bone_selection_mode == "ALL":
                        chain = []
                        if not add_bone_chain(arm, child_bone, chain):
                            continue
                        bone_chains.append(chain)

    utils.object_mode_to(arm)

    return bone_chains


def smooth_hair_bone_weights(arm, obj, bone_chains, iterations):
    props = bpy.context.scene.CC3ImportProps

    if iterations == 0:
        return

    for bone in arm.data.bones:
        bone.select = False

    # select all the bones involved
    for bone_chain in bone_chains:
        for bone_def in bone_chain:
            bone_name = bone_def["name"]
            if bone_name in arm.data.bones:
                arm.data.bones[bone_name].select = True

    # Note: BONE_SELECT group select mode is only available if the armature is also selected with the active mesh
    #       (otherwise it doesn't even exist as an enum option)
    utils.set_mode("OBJECT")
    utils.try_select_objects([arm, obj], True)
    utils.set_active_object(obj)
    utils.set_mode("WEIGHT_PAINT")
    bpy.ops.object.vertex_group_smooth(group_select_mode='BONE_SELECT', factor = 1.0, repeat = iterations)
    utils.object_mode_to(obj)

    # for CC4 rigs, lock rotation and position of the first bone in each chain
    for bone_chain in bone_chains:
        bone_def = bone_chain[0]
        bone_name = bone_def["name"]
        if bone_name in arm.data.bones:
            bone : bpy.types.Bone = arm.data.bones[bone_name]
            pose_bone : bpy.types.PoseBone = arm.pose.bones[bone_name]
            if props.hair_rig_target == "CC4":
                pose_bone.lock_location = [True, True, True]
                pose_bone.lock_rotation = [True, True, True]
                pose_bone.lock_scale = [True, True, True]
                pose_bone.lock_rotation_w = True
            else:
                pose_bone.lock_location = [False, False, False]
                pose_bone.lock_rotation = [False, False, False]
                pose_bone.lock_rotation_w = False
                pose_bone.lock_scale = [False, False, False]



def find_stroke_set_root(stroke_set, stroke, done : list):
    done.append(stroke)
    next_strokes, prev_strokes = stroke_set[stroke]
    if not prev_strokes:
        return stroke
    elif prev_strokes not in done:
        return find_stroke_set_root(stroke_set, prev_strokes[0], done)
    else:
        return None


def combine_strokes(strokes):
    stroke_set = {}

    for stroke in strokes:
        # if the last position is near the first position of another stroke...
        first = stroke.points[0].co
        last = stroke.points[-1].co
        next_strokes = []
        prev_strokes = []
        stroke_set[stroke] = [next_strokes, prev_strokes]
        for s in strokes:
            if s != stroke:
                if (s.points[0].co - last).length < STROKE_JOIN_THRESHOLD:
                    next_strokes.append(s)
                if (s.points[-1].co - first).length < STROKE_JOIN_THRESHOLD:
                    prev_strokes.append(s)

    stroke_roots = set()
    for stroke in strokes:
        root = find_stroke_set_root(stroke_set, stroke, [])
        if root:
            stroke_roots.add(root)

    return stroke_set, stroke_roots


def stroke_root_to_loop(stroke_set, stroke, loop : list):
    next_strokes, prev_strokes = stroke_set[stroke]
    for p in stroke.points:
        loop.append(p.co)
    if next_strokes:
        stroke_root_to_loop(stroke_set, next_strokes[0], loop)


# TODO if the loop length is less than 30? subdivide until it is greater, (so the smoothing works better)
def subdivide_loop(loop):
    subd = []
    for i in range(0, len(loop) - 1):
        l0 = loop[i]
        l2 = loop[i + 1]
        l1 = (l0 + l2) * 0.5
        subd.append(l0)
        subd.append(l1)
    subd.append(loop[-1])
    loop.clear()
    for co in subd:
        loop.append(co)


def smooth_loop(loop):
    strength = 0.5
    #iterations = min(10, max(1, int(len(loop) / 5)))
    iterations = 10
    smoothed_loop = loop.copy()
    for i in range(0, iterations):
        for l in range(0, len(loop)):
            smoothed_loop[l] = loop[l]
        for l in range(1, len(loop)-1):
            smoothed = (loop[l - 1] + loop[l] + loop[l + 1]) / 3.0
            original = loop[l]
            smoothed_loop[l] = (smoothed - original) * strength + original
        for l in range(0, len(loop)):
            loop[l] = smoothed_loop[l]


def greased_pencil_to_length_loops(bone_length):
    current_frame = bpy.context.scene.frame_current

    grease_pencil_layer = get_active_grease_pencil_layer()
    if not grease_pencil_layer:
        return

    frame = grease_pencil_layer.active_frame
    stroke_set, stroke_roots = combine_strokes(frame.strokes)

    loops = []
    for root in stroke_roots:
        loop = []
        stroke_root_to_loop(stroke_set, root, loop)
        if len(loop) > 1 and loop_length(loop) >= bone_length / 2:
            while(len(loop) < 25):
                subdivide_loop(loop)
            smooth_loop(loop)
            loops.append(loop)

    return loops


def grease_pencil_to_bones(chr_cache, arm, parent_mode, bone_length = 0.05, skip_length = 0.0):

    grease_pencil_layer = get_active_grease_pencil_layer()
    if not grease_pencil_layer:
        return

    #mode_selection = utils.store_mode_selection_state()
    arm_pose = reset_pose(arm)

    repair_orphaned_hair_bones(chr_cache, arm)

    bones.show_armature_layers(arm, [25], in_front=True)

    hair_bone_prefix = get_hair_bone_prefix(parent_mode)

    # check root bone exists...
    root_bone_name = get_root_bone_name(chr_cache, arm, parent_mode)
    root_bone = bones.get_pose_bone(arm, root_bone_name)

    if root_bone:
        loops = greased_pencil_to_length_loops(bone_length)
        utils.edit_mode_to(arm)
        remove_existing_loop_bones(chr_cache, arm, loops)
        for edit_bone in arm.data.edit_bones:
            edit_bone.select_head = False
            edit_bone.select_tail = False
            edit_bone.select = False
        loop_index = 1
        new_bones = []
        for loop in loops:
            loop_index = find_unused_hair_bone_index(arm, loop_index, hair_bone_prefix)
            if loop_to_bones(chr_cache, arm, parent_mode, loop, loop_index, bone_length, skip_length, new_bones):
                loop_index += 1

    remove_duplicate_bones(chr_cache, arm)

    utils.object_mode_to(arm)

    restore_pose(arm, arm_pose)
    #utils.restore_mode_selection_state(mode_selection)
    utils.edit_mode_to(arm)
    bpy.ops.wm.tool_set_by_id(name="builtin.annotate")


def get_active_grease_pencil_layer():
    #current_frame = bpy.context.scene.frame_current
    #note_layer = bpy.data.grease_pencils['Annotations'].layers.active
    #frame = note_layer.active_frame
    try:
        return bpy.context.scene.grease_pencil.layers.active
    except:
        return None


def clear_greased_pencil():
    active_layer = get_active_grease_pencil_layer()
    if active_layer:
        active_layer.active_frame.clear()


def add_custom_bone(chr_cache, arm, parent_mode, bone_length = 0.05, skip_length = 0.0):

    arm_pose = reset_pose(arm)

    repair_orphaned_hair_bones(chr_cache, arm)

    bones.show_armature_layers(arm, [25], in_front=True)

    hair_bone_prefix = get_hair_bone_prefix(parent_mode)

    # check root bone exists...
    root_bone_name = get_root_bone_name(chr_cache, arm, parent_mode)
    root_bone = bones.get_pose_bone(arm, root_bone_name)

    if root_bone:
        utils.edit_mode_to(arm)
        for edit_bone in arm.data.edit_bones:
            edit_bone.select_head = False
            edit_bone.select_tail = False
            edit_bone.select = False
        loop_index = 1
        new_bones = []
        loop_index = find_unused_hair_bone_index(arm, loop_index, hair_bone_prefix)
        if custom_bone(chr_cache, arm, parent_mode, loop_index, bone_length, new_bones):
            loop_index += 1

    utils.object_mode_to(arm)
    restore_pose(arm, arm_pose)

    remove_duplicate_bones(chr_cache, arm)

    utils.edit_mode_to(arm)


def bind_cards_to_bones(chr_cache, arm, objects, card_dir : Vector, max_radius, max_bones, max_weight, curve, variance, existing_scale, card_mode, bone_mode, smoothing):

    utils.object_mode_to(arm)
    reset_pose(arm)
    remove_duplicate_bones(chr_cache, arm)
    bone_chains = get_bone_chains(chr_cache, arm, bone_mode)

    hair_bones = []
    for bone_chain in bone_chains:
        for bone_def in bone_chain:
            hair_bones.append(bone_def["name"])

    for obj in objects:
        remove_hair_bone_weights(arm, obj, hair_bone_list=hair_bones)
        bm, cards = get_hair_cards_lateral(chr_cache, obj, card_dir, card_mode)
        scale_existing_weights(obj, bm, existing_scale)
        assign_bones(obj, bm, cards, bone_chains, max_radius, max_bones, max_weight, curve, variance)
        bm.to_mesh(obj.data)

        smooth_hair_bone_weights(arm, obj, bone_chains, smoothing)

    arm.data.pose_position = "POSE"
    utils.pose_mode_to(arm)


def is_hair_rig_accessory(objects):

    is_hair_rig = False
    is_accessory = True

    if type(objects) is list:

        for obj in objects:
            if obj.type == "MESH":
                for vg in obj.vertex_groups:
                    if is_hair_bone(vg.name):
                        is_hair_rig = True
                    else:
                        is_accessory = False

    else:

        for vg in objects.vertex_groups:
            if is_hair_bone(vg.name):
                is_hair_rig = True
            else:
                is_accessory = False

    return is_hair_rig, is_accessory



def convert_hair_rigs_to_accessory(chr_cache, arm, objects):
    """Removes all none hair rig vertex groups from objects so that CC4 recognizes them as accessories
       and not cloth or hair.\n\n
       Accessories are categorized by:\n
            1. A bone representing the accessory parented to a CC Base bone.
            2. Child accessory deformation bone(s) parented to the accessory bone in 1.
            3. Object(s) with vertex weights to ONLY these accessory deformation bones in 2.
            4. All vertices in the accessory must be weighted.
    """
    groups_to_remove = []

    for obj in objects:

        # make sure it's a hair rig
        is_hair_rig, is_accessory = is_hair_rig_accessory(obj)

        # determine non-hair rig vertex groups
        if is_hair_rig and not is_accessory:
            for vg in obj.vertex_groups:
                if not is_hair_bone(vg.name):
                    groups_to_remove.append(vg)

    # remove non-hair rig vertex groups
    for vg in groups_to_remove:
        obj.vertex_groups.remove(vg)

    return


def deselect_invalid_materials(chr_cache, obj):
    """Mesh polygon selection only works in OBJECT mode"""
    if utils.object_exists_is_mesh(obj):
        for slot in obj.material_slots:
            mat = slot.material
            mat_cache = chr_cache.get_material_cache(mat)
            if mat_cache:
                if mat_cache.material_type == "SCALP":
                    meshutils.select_material_faces(obj, mat, False)


def reset_pose(arm):
    arm_pose = arm.data.pose_position
    arm.data.pose_position = "REST"
    return arm_pose


def restore_pose(arm, arm_pose):
    arm.data.pose_position = arm_pose


class CC3OperatorHair(bpy.types.Operator):
    """Blender Hair Functions"""
    bl_idname = "cc3.hair"
    bl_label = "Blender Hair Functions"
    #bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    param: bpy.props.StringProperty(
            name = "param",
            default = ""
        )

    def execute(self, context):
        props = bpy.context.scene.CC3ImportProps
        prefs = bpy.context.preferences.addons[__name__.partition(".")[0]].preferences

        if self.param == "CARDS_TO_CURVES":

            chr_cache = props.get_context_character_cache(context)
            selected_cards_to_curves(chr_cache, bpy.context.active_object,
                                     props.hair_dir_vector(),
                                     one_loop_per_card = props.hair_curve_merge_loops == "MERGE")

        if self.param == "ADD_BONES":

            chr_cache = props.get_context_character_cache(context)
            arm = chr_cache.get_armature()
            hair_obj = bpy.context.active_object

            if utils.object_exists_is_mesh(hair_obj) and utils.object_exists_is_armature(arm):
                selected_cards_to_bones(chr_cache, arm,
                                        hair_obj,
                                        props.hair_rig_bone_root,
                                        props.hair_dir_vector(),
                                        one_loop_per_card = True,
                                        bone_length = props.hair_rig_bone_length / 100.0,
                                        skip_length = props.hair_rig_bind_skip_length / 100.0)
            else:
                self.report({"ERROR"}, "Active Object must be a mesh!")

        if self.param == "ADD_BONES_GREASE":

            chr_cache = props.get_context_character_cache(context)
            arm = chr_cache.get_armature()

            if chr_cache and utils.object_exists_is_armature(arm):
                grease_pencil_to_bones(chr_cache, arm, props.hair_rig_bone_root,
                                       bone_length = props.hair_rig_bone_length / 100.0,
                                       skip_length = props.hair_rig_bind_skip_length / 100.0)
            else:
                self.report({"ERROR"}, "Active Object be part of the character!")

        if self.param == "ADD_BONES_CUSTOM":

            chr_cache = props.get_context_character_cache(context)
            arm = chr_cache.get_armature()

            if chr_cache and utils.object_exists_is_armature(arm):
                add_custom_bone(chr_cache, arm, props.hair_rig_bone_root,
                                bone_length = props.hair_rig_bone_length / 100.0)

            else:
                self.report({"ERROR"}, "Active Object be part of the character!")

        if self.param == "REMOVE_HAIR_BONES":

            mode_selection = utils.store_mode_selection_state()

            chr_cache = props.get_context_character_cache(context)
            arm = utils.get_armature_in_objects(bpy.context.selected_objects)
            if not arm:
                arm = chr_cache.get_armature()

            objects = [ obj for obj in bpy.context.selected_objects if utils.object_exists_is_mesh(obj) ]

            if utils.object_exists_is_armature(arm):
                remove_hair_bones(chr_cache, arm, objects, props.hair_rig_bind_bone_mode)
                utils.restore_mode_selection_state(mode_selection)

        if self.param == "BIND_TO_BONES":

            chr_cache = props.get_context_character_cache(context)
            arm = utils.get_armature_in_objects(bpy.context.selected_objects)
            if not arm:
                arm = chr_cache.get_armature()

            objects = [ obj for obj in bpy.context.selected_objects if utils.object_exists_is_mesh(obj) ]

            seed = props.hair_rig_bind_seed
            random.seed(seed)

            existing_scale = props.hair_rig_bind_existing_scale
            if props.hair_rig_target == "CC4":
                existing_scale = 0.0

            if utils.object_exists_is_armature(arm) and objects:
                bind_cards_to_bones(chr_cache, arm,
                                    objects,
                                    props.hair_dir_vector(),
                                    props.hair_rig_bind_bone_radius / 100.0,
                                    props.hair_rig_bind_bone_count,
                                    props.hair_rig_bind_bone_weight,
                                    props.hair_rig_bind_weight_curve,
                                    props.hair_rig_bind_bone_variance,
                                    existing_scale,
                                    props.hair_rig_bind_card_mode,
                                    props.hair_rig_bind_bone_mode,
                                    props.hair_rig_bind_smoothing)
            else:
                self.report({"ERROR"}, "Selected Object(s) to bind must be Meshes!")

            if props.hair_rig_target == "CC4":
                props.hair_rig_bind_existing_scale = 0.0

                # for CC4 rigs, convert the hair meshes to accesories
                convert_hair_rigs_to_accessory(chr_cache, arm, objects)
            else:
                props.hair_rig_bind_existing_scale = 1.0

        if self.param == "CLEAR_WEIGHTS":

            mode_selection = utils.store_mode_selection_state()

            chr_cache = props.get_context_character_cache(context)
            arm = utils.get_armature_in_objects(bpy.context.selected_objects)
            if not arm:
                arm = chr_cache.get_armature()

            objects = [ obj for obj in bpy.context.selected_objects if utils.object_exists_is_mesh(obj) ]

            if utils.object_exists_is_armature(arm) and objects:
                clear_hair_bone_weights(chr_cache, arm, objects, props.hair_rig_bind_bone_mode)
                utils.restore_mode_selection_state(mode_selection)
            else:
                self.report({"ERROR"}, "Selected Object(s) to clear weights must be Meshes!")

        if self.param == "CLEAR_GREASE_PENCIL":

            clear_greased_pencil()

        if self.param == "MAKE_ACCESSORY":

            chr_cache = props.get_context_character_cache(context)
            arm = utils.get_armature_in_objects(bpy.context.selected_objects)
            if not arm:
                arm = chr_cache.get_armature()

            objects = [ obj for obj in bpy.context.selected_objects if utils.object_exists_is_mesh(obj) ]

            if utils.object_exists_is_armature(arm) and objects:
                convert_hair_rigs_to_accessory(chr_cache, arm, objects)

        return {"FINISHED"}

    @classmethod
    def description(cls, context, properties):

        if properties.param == "ADD_BONES":
            return "Add bones to the hair rig, generated from the selected hair cards in the active mesh"
        elif properties.param == "ADD_BONES_CUSTOM":
            return "Add a single custom bone to the hair rig"
        elif properties.param == "ADD_BONES_GREASE":
            return "Add bones generated from grease pencil lines drawn in the current annotation layer.\n\n" \
                   "Note: For best results draw lines onto the hair in Surface placement mode."
        elif properties.param == "REMOVE_HAIR_BONES":
            return "Remove bones from the hair rig.\n\n" \
                   "Bone selection mode determines if only selected bones are removed or if all bones are removed.\n\n" \
                   "Any associated vertex weights will also be removed from the hair meshes\n\n" \
                   "Note: Selecting any bone in a chain will use the entire chain of bones"
        elif properties.param == "BIND_TO_BONES":
            return "Bind the selected hair meshes to the hair rig bones.\n\n" \
                   "Bone selection mode determines if only the selected bones are used to bind vertex weights or if all bones are used.\n\n" \
                   "Card selection mode determines if only selected hair cards in the selected hair meshes or all the hair cards are weighted.\n\n" \
                   "Note: Selecting any part of a hair card or any bone in a chain will use the entire card and/or chain of bones"
        elif properties.param == "CLEAR_WEIGHTS":
            return "Clear the hair rig bone vertex weights from the selected hair meshes.\n\n" \
                   "Bone selection mode determines if only the selected bones weights are removed or if all the hair rig bones weights are removed.\n\n" \
                   "If no meshes are selected then *all* meshes in the character will be cleared of the hair rig vertex weights.\n\n" \
                   "Note: Selecting any bone in a chain will use the entire chain of bones"
        elif properties.param == "CLEAR_GREASE_PENCIL":
            return "Remove all grease pencil lines from the current annotation layer"
        elif properties.param == "CARDS_TO_CURVES":
            return "Convert all the hair cards into curves"
        elif properties.param == "MAKE_ACCESSORY":
            return "Removes all none hair rig vertex groups from objects so that CC4 recognizes them as accessories and not cloth or hair.\n\n" \
                   "Accessories are categorized by:\n" \
                   "    1. A bone representing the accessory parented to a CC Base bone.\n" \
                   "    2. Child accessory deformation bone(s) parented to the accessory bone in 1.\n" \
                   "    3. Object(s) with vertex weights to ONLY these accessory deformation bones in 2.\n" \
                   "    4. All vertices in the accessory must be weighted"

        return ""


class CC3ExportHair(bpy.types.Operator):
    """Export Hair Curves"""
    bl_idname = "cc3.export_hair"
    bl_label = "Export Hair"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Base filepath used for exporting the hair curves",
        maxlen=1024,
        subtype='FILE_PATH',
        )

    filename_ext = ""  # ExportHelper mixin class uses this

    #filter_glob: bpy.props.StringProperty(
    #    default="*.fbx;*.obj;*.blend",
    #    options={"HIDDEN"},
    #    )

    def execute(self, context):
        props = bpy.context.scene.CC3ImportProps
        prefs = bpy.context.preferences.addons[__name__.partition(".")[0]].preferences

        objects = bpy.context.selected_objects.copy()
        chr_cache = props.get_any_character_cache_from_objects(objects, True)

        export_blender_hair(self, chr_cache, objects, self.filepath)

        return {"FINISHED"}


    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


    @classmethod
    def description(cls, context, properties):
        return "Export the hair curves to Alembic."