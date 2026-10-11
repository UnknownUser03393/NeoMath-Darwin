#!/usr/bin/env python3
"""Generate the Xcode project with the pinned SwiftMath package, including the existing C++ core."""
from pathlib import Path
import hashlib
root = Path(__file__).resolve().parents[1]
def uid(s): return hashlib.sha1(s.encode()).hexdigest()[:24].upper()
def q(s): return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'
objects = {}
def put(name, body):
    key = uid(name); objects[key] = '{ ' + body + ' };'; return key
files = sorted((root/'NeoMathDarwin').rglob('*.swift')) + sorted((root/'NeoMathDarwin/Core').glob('*.mm'))
core = root.parent/'desktop/cpp'
files += sorted((core/'src').rglob('*.cpp'))
refs, builds = [], []
for f in files:
    import os
    path = os.path.relpath(f, root)
    kind = {'swift':'sourcecode.swift','mm':'sourcecode.cpp.objcpp','cpp':'sourcecode.cpp.cpp'}[f.suffix[1:]]
    ref = put(path, f'isa = PBXFileReference; lastKnownFileType = {kind}; path = {q(path)}; sourceTree = SOURCE_ROOT;')
    refs.append(ref)
    builds.append(put(path+'build', f'isa = PBXBuildFile; fileRef = {ref};'))
product = put('product', 'isa = PBXFileReference; explicitFileType = wrapper.application; path = NeoMathDarwin.app; sourceTree = BUILT_PRODUCTS_DIR;')
group = put('group', 'isa = PBXGroup; children = (' + ','.join(refs+[product,uid('PreviewAssets')]) + '); sourceTree = "<group>";')
sources = put('sources', 'isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ('+','.join(builds)+'); runOnlyForDeploymentPostprocessing = 0;')
package = put('SwiftMath-package', 'isa = XCRemoteSwiftPackageReference; repositoryURL = "https://github.com/mgriebling/SwiftMath.git"; requirement = { kind = revision; revision = "1d2c90827e9c3908269d810d055fb03b7da5fd53"; };')
packageproduct = put('SwiftMath-product', f'isa = XCSwiftPackageProductDependency; package = {package}; productName = SwiftMath;')
packagebuild = put('SwiftMath-build', f'isa = PBXBuildFile; productRef = {packageproduct};')
frameworks = put('frameworks', 'isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (' + packagebuild + '); runOnlyForDeploymentPostprocessing = 0;')
assets = put('PreviewAssets', 'isa = PBXFileReference; lastKnownFileType = folder; path = NeoMathDarwin/PreviewAssets; sourceTree = SOURCE_ROOT;')
assetbuild = put('PreviewAssets-build', f'isa = PBXBuildFile; fileRef = {assets};')
resources = put('resources', 'isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (' + assetbuild + '); runOnlyForDeploymentPostprocessing = 0;')
settings = {
 'PRODUCT_NAME':'$(TARGET_NAME)', 'PRODUCT_BUNDLE_IDENTIFIER':'com.unknownuser.NeoMathDarwin',
 'IPHONEOS_DEPLOYMENT_TARGET':'17.0','TARGETED_DEVICE_FAMILY':'2','SDKROOT':'iphoneos',
 'SUPPORTED_PLATFORMS':'iphoneos iphonesimulator','SWIFT_VERSION':'5.0','CLANG_CXX_LANGUAGE_STANDARD':'c++20',
 'CLANG_ENABLE_MODULES':'YES','CLANG_ENABLE_OBJC_ARC':'YES','GENERATE_INFOPLIST_FILE':'YES',
 'INFOPLIST_KEY_UIApplicationSceneManifest_Generation':'NO','INFOPLIST_FILE':'NeoMathDarwin/Info.plist','INFOPLIST_KEY_UILaunchScreen_Generation':'YES',
 'INFOPLIST_KEY_UISupportedInterfaceOrientations_iPad':'UIInterfaceOrientationPortrait UIInterfaceOrientationPortraitUpsideDown UIInterfaceOrientationLandscapeLeft UIInterfaceOrientationLandscapeRight',
 'INFOPLIST_KEY_CFBundleDisplayName':'NeoMath','INFOPLIST_KEY_LSSupportsOpeningDocumentsInPlace':'YES',
 'SWIFT_OBJC_BRIDGING_HEADER':'NeoMathDarwin/NeoMathDarwin-Bridging-Header.h',
 'HEADER_SEARCH_PATHS':'$(SRCROOT)/../desktop/cpp/include','CODE_SIGN_STYLE':'Automatic',
 'CURRENT_PROJECT_VERSION':'1','MARKETING_VERSION':'0.1.0', 'ENABLE_USER_SCRIPT_SANDBOXING':'YES',
}
configs = []
for mode in ['Debug','Release']:
    config = dict(settings, SWIFT_OPTIMIZATION_LEVEL='-Onone' if mode=='Debug' else '-O', GCC_OPTIMIZATION_LEVEL='0' if mode=='Debug' else 's')
    if mode == 'Debug': config['SWIFT_ACTIVE_COMPILATION_CONDITIONS'] = 'DEBUG'
    configs.append(put(mode, 'isa = XCBuildConfiguration; buildSettings = {' + ''.join(k+' = '+q(v)+';' for k,v in config.items()) + '}; name = '+mode+';'))
configlist = put('configs','isa = XCConfigurationList; buildConfigurations = ('+','.join(configs)+'); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release;')
target = put('target', f'isa = PBXNativeTarget; buildConfigurationList = {configlist}; buildPhases = ({sources},{frameworks},{resources}); buildRules = (); dependencies = (); name = NeoMathDarwin; productName = NeoMathDarwin; productReference = {product}; productType = "com.apple.product-type.application"; packageProductDependencies = ({packageproduct});')
project = put('project',f'isa = PBXProject; attributes = {{ LastUpgradeCheck = 1640; }}; buildConfigurationList = {configlist}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en, Base); mainGroup = {group}; projectDirPath = ""; projectRoot = ""; targets = ({target}); packageReferences = ({package});')
out = root/'NeoMathDarwin.xcodeproj'
out.mkdir(exist_ok=True)
(out/'project.pbxproj').write_text('// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n'+ '\n'.join(k+' = '+v for k,v in objects.items())+'\n}; rootObject = '+project+'; }\n')
schemes = out/'xcshareddata/xcschemes'; schemes.mkdir(parents=True,exist_ok=True)
(schemes/'NeoMathDarwin.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="1640" version="1.3">
<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="NeoMathDarwin.app" BlueprintName="NeoMathDarwin" ReferencedContainer="container:NeoMathDarwin.xcodeproj"/></BuildActionEntry></BuildActionEntries></BuildAction>
<LaunchAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" allowLocationSimulation="YES"><BuildableProductRunnable runnableDebuggingMode="0"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="NeoMathDarwin.app" BlueprintName="NeoMathDarwin" ReferencedContainer="container:NeoMathDarwin.xcodeproj"/></BuildableProductRunnable></LaunchAction>
<ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"/>
<AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>''')
print(out)
