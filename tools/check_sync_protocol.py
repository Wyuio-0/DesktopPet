"""Compile/run the native Android HTTP boundary tests using Gradle's cached Kotlin compiler.

Run after a Gradle Android build; no Android emulator or extra test dependency is needed.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gradle-home", default=os.environ.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cache = Path(args.gradle_home) / "caches/modules-2/files-2.1"
    version = re.search(r'org.jetbrains.kotlin.android"\) version "([^"]+)"', (root / "android/build.gradle.kts").read_text()).group(1)

    def artifact(group, name, ver, compatible=False):
        files = list((cache / group / name / ver).glob("*/*.jar"))
        if not files and compatible:
            # Gradle may resolve a newer shared runtime through another plugin.
            candidates = list((cache / group / name).glob("*/*/*.jar"))
            files = sorted(candidates, key=lambda p: tuple(map(int, re.findall(r"\d+", p.parents[1].name))), reverse=True)
        if not files:
            raise RuntimeError(f"Missing cached {name} {ver}; run the Android Gradle build first")
        return files[0]

    compiler = artifact("org.jetbrains.kotlin", "kotlin-compiler-embeddable", version)
    # Runtime dependencies of the project's pinned Kotlin 2.0.21 compiler.
    # Gradle may retain the jars without their original POM files.
    if version != "2.0.21":
        raise RuntimeError("Update the compiler runtime dependency list when upgrading Kotlin")
    jars = [compiler] + [artifact("org.jetbrains.kotlin", name, version) for name in
                         ("kotlin-stdlib", "kotlin-script-runtime", "kotlin-daemon-embeddable")]
    jars.extend((artifact("org.jetbrains.kotlin", "kotlin-reflect", "1.6.10", compatible=True),
                 artifact("org.jetbrains.intellij.deps", "trove4j", "1.0.20200330", compatible=True),
                 artifact("org.jetbrains.kotlinx", "kotlinx-coroutines-core-jvm", "1.6.4", compatible=True)))
    annotations = artifact("org.jetbrains", "annotations", "13.0", compatible=True)
    jars.append(annotations)
    stdlib = artifact("org.jetbrains.kotlin", "kotlin-stdlib", version)
    java = str(Path(os.environ["JAVA_HOME"]) / "bin/java") if os.environ.get("JAVA_HOME") else shutil.which("java")
    if not java:
        raise RuntimeError("JDK is required")
    with tempfile.TemporaryDirectory(prefix="amiya-sync-jvm-") as temp:
        output = str(Path(temp) / "checks.jar")
        subprocess.run([java, "-cp", os.pathsep.join(map(str, jars)),
                        "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect",
                        "-classpath", os.pathsep.join(map(str, (stdlib, annotations))), "-d", output,
                        str(root / "android/app/src/main/java/com/amiya/pet/core/sync/SyncHttpProtocol.kt"),
                        str(root / "android/app/src/main/java/com/amiya/pet/core/sync/SyncCrypto.kt"),
                        str(root / "android/tools/SyncHttpProtocolCheck.kt"),
                        str(root / "android/tools/SyncCryptoCheck.kt")], check=True)
        subprocess.run([java, "-cp", os.pathsep.join((output, str(stdlib))),
                        "com.amiya.pet.core.sync.SyncHttpProtocolCheckKt",
                        str(root / "tests/fixtures/sync_v2_vectors.tsv")], check=True)


if __name__ == "__main__":
    main()
