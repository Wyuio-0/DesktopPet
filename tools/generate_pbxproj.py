"""
Generate a complete, valid Xcode project file (project.pbxproj) for AmiyaPet-iOS.
"""
import os
import hashlib
from pathlib import Path

def generate_id(name: str) -> str:
    """Generate deterministic 24-character hex ID for PBX objects."""
    h = hashlib.md5(name.encode('utf-8')).hexdigest()
    return h[:24].upper()

def main():
    base_dir = Path("ios/AmiyaPet")
    proj_dir = Path("ios/AmiyaPet.xcodeproj")
    proj_dir.mkdir(parents=True, exist_ok=True)
    shared_data = proj_dir / "xcshareddata" / "xcschemes"
    shared_data.mkdir(parents=True, exist_ok=True)

    # 1. Collect all Swift files
    swift_files = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".swift"):
                full_path = Path(root) / f
                rel_path = full_path.relative_to(base_dir).as_posix()
                swift_files.append((f, rel_path))

    # 2. Collect voice resources
    voice_files = []
    voice_dir = base_dir / "Resources" / "Voices"
    if voice_dir.exists():
        for f in os.listdir(voice_dir):
            if f.endswith(".wav"):
                voice_files.append((f, f"Resources/Voices/{f}"))

    # File references
    # ID mappings:
    # file_ref_id, build_file_id
    file_refs = {}
    build_files = {}

    for name, rel_path in swift_files:
        f_id = generate_id(f"fileref_{rel_path}")
        b_id = generate_id(f"buildfile_{rel_path}")
        file_refs[rel_path] = (f_id, name, "sourcecode.swift", "AmiyaPet/" + rel_path)
        build_files[rel_path] = (b_id, f_id, name)

    # Resource: Assets.xcassets
    assets_rel = "Resources/Assets.xcassets"
    assets_f_id = generate_id("fileref_assets")
    assets_b_id = generate_id("buildfile_assets")
    file_refs[assets_rel] = (assets_f_id, "Assets.xcassets", "folder.assetcatalog", "AmiyaPet/" + assets_rel)
    build_files[assets_rel] = (assets_b_id, assets_f_id, "Assets.xcassets")

    # Resource: Info.plist
    plist_rel = "Resources/Info.plist"
    plist_f_id = generate_id("fileref_plist")
    file_refs[plist_rel] = (plist_f_id, "Info.plist", "text.plist.xml", "AmiyaPet/" + plist_rel)

    # Resource: Voices
    for name, rel_path in voice_files:
        f_id = generate_id(f"fileref_voice_{name}")
        b_id = generate_id(f"buildfile_voice_{name}")
        file_refs[rel_path] = (f_id, name, "audio.wav", "AmiyaPet/" + rel_path)
        build_files[rel_path] = (b_id, f_id, name)

    # Target & Project IDs
    target_id = generate_id("target_AmiyaPet")
    project_id = generate_id("project_AmiyaPet")
    main_group_id = generate_id("group_main")
    sources_phase_id = generate_id("phase_sources")
    frameworks_phase_id = generate_id("phase_frameworks")
    resources_phase_id = generate_id("phase_resources")

    debug_target_cfg_id = generate_id("cfg_target_debug")
    release_target_cfg_id = generate_id("cfg_target_release")
    target_cfg_list_id = generate_id("cfglist_target")

    debug_proj_cfg_id = generate_id("cfg_proj_debug")
    release_proj_cfg_id = generate_id("cfg_proj_release")
    proj_cfg_list_id = generate_id("cfglist_proj")

    product_file_id = generate_id("fileref_product_app")

    # Frameworks
    frameworks = [
        "ActivityKit.framework",
        "WidgetKit.framework",
        "EventKit.framework",
        "AVFoundation.framework",
        "UserNotifications.framework",
        "Network.framework",
        "SwiftUI.framework"
    ]
    framework_entries = []
    for fw in frameworks:
        fw_f_id = generate_id(f"fileref_fw_{fw}")
        fw_b_id = generate_id(f"buildfile_fw_{fw}")
        framework_entries.append((fw, fw_f_id, fw_b_id))

    # Construct project.pbxproj content
    out = []
    out.append("// !$*UTF8*$!")
    out.append("{")
    out.append("\tarchiveVersion = 1;")
    out.append("\tclasses = {")
    out.append("\t};")
    out.append("\tobjectVersion = 56;")
    out.append("\tobjects = {")
    out.append("")

    # PBXBuildFile section
    out.append("/* Begin PBXBuildFile section */")
    for rel_path, (b_id, f_id, name) in build_files.items():
        out.append(f"\t\t{b_id} /* {name} in Sources/Resources */ = {{isa = PBXBuildFile; fileRef = {f_id} /* {name} */; }};")
    for fw, fw_f_id, fw_b_id in framework_entries:
        out.append(f"\t\t{fw_b_id} /* {fw} in Frameworks */ = {{isa = PBXBuildFile; fileRef = {fw_f_id} /* {fw} */; }};")
    out.append("/* End PBXBuildFile section */")
    out.append("")

    # PBXFileReference section
    out.append("/* Begin PBXFileReference section */")
    out.append(f"\t\t{product_file_id} /* AmiyaPet.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = AmiyaPet.app; sourceTree = BUILT_PRODUCTS_DIR; }};")
    for rel_path, (f_id, name, ftype, path) in file_refs.items():
        out.append(f"\t\t{f_id} /* {name} */ = {{isa = PBXFileReference; lastKnownFileType = {ftype}; path = \"{path}\"; sourceTree = \"<group>\"; }};")
    for fw, fw_f_id, fw_b_id in framework_entries:
        out.append(f"\t\t{fw_f_id} /* {fw} */ = {{isa = PBXFileReference; lastKnownFileType = wrapper.framework; name = {fw}; path = System/Library/Frameworks/{fw}; sourceTree = SDKROOT; }};")
    out.append("/* End PBXFileReference section */")
    out.append("")

    # PBXFrameworksBuildPhase section
    out.append("/* Begin PBXFrameworksBuildPhase section */")
    out.append(f"\t\t{frameworks_phase_id} /* Frameworks */ = {{")
    out.append("\t\t\tisa = PBXFrameworksBuildPhase;")
    out.append("\t\t\tbuildActionMask = 2147483647;")
    out.append("\t\t\tfiles = (")
    for fw, fw_f_id, fw_b_id in framework_entries:
        out.append(f"\t\t\t\t{fw_b_id} /* {fw} in Frameworks */,")
    out.append("\t\t\t);")
    out.append("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
    out.append("\t\t};")
    out.append("/* End PBXFrameworksBuildPhase section */")
    out.append("")

    # PBXGroup section
    out.append("/* Begin PBXGroup section */")
    out.append(f"\t\t{main_group_id} = {{")
    out.append("\t\t\tisa = PBXGroup;")
    out.append("\t\t\tchildren = (")
    for rel_path, (f_id, name, _, _) in file_refs.items():
        out.append(f"\t\t\t\t{f_id} /* {name} */,")
    for fw, fw_f_id, _ in framework_entries:
        out.append(f"\t\t\t\t{fw_f_id} /* {fw} */,")
    out.append(f"\t\t\t\t{product_file_id} /* AmiyaPet.app */,")
    out.append("\t\t\t);")
    out.append("\t\t\tsourceTree = \"<group>\";")
    out.append("\t\t};")
    out.append("/* End PBXGroup section */")
    out.append("")

    # PBXNativeTarget section
    out.append("/* Begin PBXNativeTarget section */")
    out.append(f"\t\t{target_id} /* AmiyaPet */ = {{")
    out.append("\t\t\tisa = PBXNativeTarget;")
    out.append(f"\t\t\tbuildConfigurationList = {target_cfg_list_id} /* Build configuration list for PBXNativeTarget \"AmiyaPet\" */;")
    out.append("\t\t\tbuildPhases = (")
    out.append(f"\t\t\t\t{sources_phase_id} /* Sources */,")
    out.append(f"\t\t\t\t{frameworks_phase_id} /* Frameworks */,")
    out.append(f"\t\t\t\t{resources_phase_id} /* Resources */,")
    out.append("\t\t\t);")
    out.append("\t\t\tbuildRules = (")
    out.append("\t\t\t);")
    out.append("\t\t\tdependencies = (")
    out.append("\t\t\t);")
    out.append("\t\t\tname = AmiyaPet;")
    out.append("\t\t\tproductName = AmiyaPet;")
    out.append(f"\t\t\tproductReference = {product_file_id} /* AmiyaPet.app */;")
    out.append("\t\t\tproductType = \"com.apple.product-type.application\";")
    out.append("\t\t};")
    out.append("/* End PBXNativeTarget section */")
    out.append("")

    # PBXProject section
    out.append("/* Begin PBXProject section */")
    out.append(f"\t\t{project_id} /* Project object */ = {{")
    out.append("\t\t\tisa = PBXProject;")
    out.append("\t\t\tattributes = {")
    out.append("\t\t\t\tBuildIndependentTargetsInParallel = 1;")
    out.append("\t\t\t\tLastUpgradeCheck = 1500;")
    out.append("\t\t\t\tTargetAttributes = {")
    out.append(f"\t\t\t\t\t{target_id} = {{")
    out.append("\t\t\t\t\t\tCreatedOnToolsVersion = 15.0;")
    out.append("\t\t\t\t\t};")
    out.append("\t\t\t\t};")
    out.append("\t\t\t};")
    out.append(f"\t\t\tbuildConfigurationList = {proj_cfg_list_id} /* Build configuration list for PBXProject \"AmiyaPet\" */;")
    out.append("\t\t\tcompatibilityVersion = \"Xcode 14.0\";")
    out.append("\t\t\tdevelopmentRegion = zh_CN;")
    out.append("\t\t\thasScannedForEncodings = 0;")
    out.append("\t\t\tknownRegions = (")
    out.append("\t\t\t\ten,")
    out.append("\t\t\t\tBase,")
    out.append("\t\t\t\tzh_CN,")
    out.append("\t\t\t);")
    out.append(f"\t\t\tmainGroup = {main_group_id};")
    out.append(f"\t\t\tproductRefGroup = {main_group_id};")
    out.append("\t\t\tprojectDirPath = \"\";")
    out.append("\t\t\tprojectRoot = \"\";")
    out.append("\t\t\ttargets = (")
    out.append(f"\t\t\t\t{target_id} /* AmiyaPet */,")
    out.append("\t\t\t);")
    out.append("\t\t};")
    out.append("/* End PBXProject section */")
    out.append("")

    # PBXResourcesBuildPhase section
    out.append("/* Begin PBXResourcesBuildPhase section */")
    out.append(f"\t\t{resources_phase_id} /* Resources */ = {{")
    out.append("\t\t\tisa = PBXResourcesBuildPhase;")
    out.append("\t\t\tbuildActionMask = 2147483647;")
    out.append("\t\t\tfiles = (")
    out.append(f"\t\t\t\t{assets_b_id} /* Assets.xcassets in Resources */,")
    for name, rel_path in voice_files:
        b_id, _, _ = build_files[rel_path]
        out.append(f"\t\t\t\t{b_id} /* {name} in Resources */,")
    out.append("\t\t\t);")
    out.append("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
    out.append("\t\t};")
    out.append("/* End PBXResourcesBuildPhase section */")
    out.append("")

    # PBXSourcesBuildPhase section
    out.append("/* Begin PBXSourcesBuildPhase section */")
    out.append(f"\t\t{sources_phase_id} /* Sources */ = {{")
    out.append("\t\t\tisa = PBXSourcesBuildPhase;")
    out.append("\t\t\tbuildActionMask = 2147483647;")
    out.append("\t\t\tfiles = (")
    for name, rel_path in swift_files:
        b_id, _, _ = build_files[rel_path]
        out.append(f"\t\t\t\t{b_id} /* {name} in Sources */,")
    out.append("\t\t\t);")
    out.append("\t\t\trunOnlyForDeploymentPostprocessing = 0;")
    out.append("\t\t};")
    out.append("/* End PBXSourcesBuildPhase section */")
    out.append("")

    # XCBuildConfiguration section
    out.append("/* Begin XCBuildConfiguration section */")
    out.append(f"\t\t{debug_proj_cfg_id} /* Debug */ = {{")
    out.append("\t\t\tisa = XCBuildConfiguration;")
    out.append("\t\t\tbuildSettings = {")
    out.append("\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;")
    out.append("\t\t\t\tCLANG_ANALYZER_NONNULL = YES;")
    out.append("\t\t\t\tCLANG_ENABLE_MODULES = YES;")
    out.append("\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;")
    out.append("\t\t\t\tDEBUG_INFORMATION_FORMAT = dwarf;")
    out.append("\t\t\t\tENABLE_TESTABILITY = YES;")
    out.append("\t\t\t\tGCC_OPTIMIZATION_LEVEL = 0;")
    out.append("\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 16.1;")
    out.append("\t\t\t\tMTL_ENABLE_DEBUG_INFO = INCLUDE_SOURCE;")
    out.append("\t\t\t\tONLY_ACTIVE_ARCH = YES;")
    out.append("\t\t\t\tSDKROOT = iphoneos;")
    out.append("\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;")
    out.append("\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = \"-Onone\";")
    out.append("\t\t\t\tSWIFT_VERSION = 5.0;")
    out.append("\t\t\t};")
    out.append("\t\t\tname = Debug;")
    out.append("\t\t};")

    out.append(f"\t\t{release_proj_cfg_id} /* Release */ = {{")
    out.append("\t\t\tisa = XCBuildConfiguration;")
    out.append("\t\t\tbuildSettings = {")
    out.append("\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;")
    out.append("\t\t\t\tCLANG_ANALYZER_NONNULL = YES;")
    out.append("\t\t\t\tCLANG_ENABLE_MODULES = YES;")
    out.append("\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;")
    out.append("\t\t\t\tDEBUG_INFORMATION_FORMAT = \"dwarf-with-dsym\";")
    out.append("\t\t\t\tENABLE_NS_ASSERTIONS = NO;")
    out.append("\t\t\t\tGCC_OPTIMIZATION_LEVEL = s;")
    out.append("\t\t\t\tIPHONEOS_DEPLOYMENT_TARGET = 16.1;")
    out.append("\t\t\t\tMTL_ENABLE_DEBUG_INFO = NO;")
    out.append("\t\t\t\tSDKROOT = iphoneos;")
    out.append("\t\t\t\tSWIFT_COMPILATION_MODE = wholemodule;")
    out.append("\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = \"-O\";")
    out.append("\t\t\t\tSWIFT_VERSION = 5.0;")
    out.append("\t\t\t\tVALIDATE_PRODUCT = YES;")
    out.append("\t\t\t};")
    out.append("\t\t\tname = Release;")
    out.append("\t\t};")

    out.append(f"\t\t{debug_target_cfg_id} /* Debug */ = {{")
    out.append("\t\t\tisa = XCBuildConfiguration;")
    out.append("\t\t\tbuildSettings = {")
    out.append("\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;")
    out.append("\t\t\t\tCODE_SIGN_STYLE = Automatic;")
    out.append("\t\t\t\tCURRENT_PROJECT_VERSION = 214;")
    out.append("\t\t\t\tGENERATE_INFOPLIST_FILE = NO;")
    out.append("\t\t\t\tINFOPLIST_FILE = AmiyaPet/Resources/Info.plist;")
    out.append("\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (\"$(inherited)\", \"@executable_path/Frameworks\");")
    out.append("\t\t\t\tMARKETING_VERSION = 1.9.4;")
    out.append("\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.amiya.pet;")
    out.append("\t\t\t\tPRODUCT_NAME = \"$(TARGET_NAME)\";")
    out.append("\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;")
    out.append("\t\t\t\tTARGETED_DEVICE_FAMILY = \"1,2\";")
    out.append("\t\t\t};")
    out.append("\t\t\tname = Debug;")
    out.append("\t\t};")

    out.append(f"\t\t{release_target_cfg_id} /* Release */ = {{")
    out.append("\t\t\tisa = XCBuildConfiguration;")
    out.append("\t\t\tbuildSettings = {")
    out.append("\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;")
    out.append("\t\t\t\tCODE_SIGN_STYLE = Automatic;")
    out.append("\t\t\t\tCURRENT_PROJECT_VERSION = 214;")
    out.append("\t\t\t\tGENERATE_INFOPLIST_FILE = NO;")
    out.append("\t\t\t\tINFOPLIST_FILE = AmiyaPet/Resources/Info.plist;")
    out.append("\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (\"$(inherited)\", \"@executable_path/Frameworks\");")
    out.append("\t\t\t\tMARKETING_VERSION = 1.9.4;")
    out.append("\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = com.amiya.pet;")
    out.append("\t\t\t\tPRODUCT_NAME = \"$(TARGET_NAME)\";")
    out.append("\t\t\t\tSWIFT_EMIT_LOC_STRINGS = YES;")
    out.append("\t\t\t\tTARGETED_DEVICE_FAMILY = \"1,2\";")
    out.append("\t\t\t};")
    out.append("\t\t\tname = Release;")
    out.append("\t\t};")
    out.append("/* End XCBuildConfiguration section */")
    out.append("")

    # XCConfigurationList section
    out.append("/* Begin XCConfigurationList section */")
    out.append(f"\t\t{proj_cfg_list_id} /* Build configuration list for PBXProject \"AmiyaPet\" */ = {{")
    out.append("\t\t\tisa = XCConfigurationList;")
    out.append("\t\t\tbuildConfigurations = (")
    out.append(f"\t\t\t\t{debug_proj_cfg_id} /* Debug */,")
    out.append(f"\t\t\t\t{release_proj_cfg_id} /* Release */,")
    out.append("\t\t\t);")
    out.append("\t\t\tdefaultConfigurationIsVisible = 0;")
    out.append("\t\t\tdefaultConfigurationName = Release;")
    out.append("\t\t};")

    out.append(f"\t\t{target_cfg_list_id} /* Build configuration list for PBXNativeTarget \"AmiyaPet\" */ = {{")
    out.append("\t\t\tisa = XCConfigurationList;")
    out.append("\t\t\tbuildConfigurations = (")
    out.append(f"\t\t\t\t{debug_target_cfg_id} /* Debug */,")
    out.append(f"\t\t\t\t{release_target_cfg_id} /* Release */,")
    out.append("\t\t\t);")
    out.append("\t\t\tdefaultConfigurationIsVisible = 0;")
    out.append("\t\t\tdefaultConfigurationName = Release;")
    out.append("\t\t};")
    out.append("/* End XCConfigurationList section */")
    out.append("")

    out.append("\t};")
    out.append(f"\trootObject = {project_id} /* Project object */;")
    out.append("}")
    out.append("")

    pbxproj_path = proj_dir / "project.pbxproj"
    with open(pbxproj_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"Written project.pbxproj ({len(out)} lines)")

    # 3. Create scheme file (AmiyaPet.xcscheme)
    scheme_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Scheme
   LastUpgradeVersion = "1500"
   version = "1.7">
   <BuildAction
      parallelizeBuildables = "YES"
      buildImplicitDependencies = "YES">
      <BuildActionEntries>
         <BuildActionEntry
            buildForTesting = "YES"
            buildForRunning = "YES"
            buildForProfiling = "YES"
            buildForArchiving = "YES"
            buildForAnalyzing = "YES">
            <BuildableReference
               BuildableIdentifier = "primary"
               BlueprintIdentifier = "{target_id}"
               BuildableName = "AmiyaPet.app"
               BlueprintName = "AmiyaPet"
               ReferencedContainer = "container:AmiyaPet.xcodeproj">
            </BuildableReference>
         </BuildActionEntry>
      </BuildActionEntries>
   </BuildAction>
   <LaunchAction
      buildConfiguration = "Debug"
      selectedDebuggerIdentifier = "Xcode.DebuggerFoundation.Debugger.LLDB"
      selectedLauncherIdentifier = "Xcode.DebuggerFoundation.Launcher.LLDB"
      launchStyle = "0"
      useCustomWorkingDirectory = "NO"
      ignoresPersistentStateOnLaunch = "NO"
      debugDocumentVersioning = "YES"
      debugServiceExtension = "internal"
      allowLocationSimulation = "YES">
      <BuildableProductRunnable
         runnableDebuggingMode = "0">
         <BuildableReference
            BuildableIdentifier = "primary"
            BlueprintIdentifier = "{target_id}"
            BuildableName = "AmiyaPet.app"
            BlueprintName = "AmiyaPet"
            ReferencedContainer = "container:AmiyaPet.xcodeproj">
         </BuildableReference>
      </BuildableProductRunnable>
   </LaunchAction>
   <ArchiveAction
      buildConfiguration = "Release"
      revealArchiveInOrganizer = "YES">
   </ArchiveAction>
</Scheme>
"""
    scheme_path = shared_data / "AmiyaPet.xcscheme"
    with open(scheme_path, "w", encoding="utf-8") as f:
        f.write(scheme_content)
    print(f"Written AmiyaPet.xcscheme")

if __name__ == "__main__":
    main()
