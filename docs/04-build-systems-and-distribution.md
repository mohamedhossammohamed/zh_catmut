# **Native Extension Architecture for Python: Build Systems, Cross-Platform Distribution, and Dynamic Loading**

## **1\. Introduction and Architectural Imperative**

The convergence of high-performance data processing frameworks within the Python ecosystem has established the Arrow C Data Interface as the paramount standard for zero-copy memory exchange.1 For analytical workloads, particularly those involving the in-place modification of Pandas Categorical memory arrays, executing operations at native machine speed while avoiding the Global Interpreter Lock (GIL) is an architectural necessity.2 Achieving this paradigm requires the deployment of natively compiled extensions that expose a strictly defined C Application Binary Interface (C-ABI).1  
While traditional Python extensions are authored in C, C++, or Rust, modern toolchains such as Zig and.NET NativeAOT (C\#) offer compelling alternatives.4 These languages provide superior cross-compilation capabilities, robust standard libraries, and stringent memory safety paradigms while maintaining full C-ABI compatibility.4 However, orchestrating the build, packaging, and distribution of non-C/C++ native binaries into standard Python wheels—ensuring seamless pip install functionality for data scientists without local compiler requirements—presents a complex continuous integration challenge.6  
This comprehensive technical analysis evaluates the architectural requirements for integrating Zig and C\# NativeAOT into standard Python packaging workflows.7 The report systematically addresses build system orchestration utilizing setuptools and scikit-build-core, cross-platform compilation matrices driven by cibuildwheel within GitHub Actions, and the intricate runtime mechanics of dynamic library loading and PyCapsule initialization via the Arrow C Data Interface.9

## **2\. Native Extension Build System Orchestration**

The foundational challenge in packaging native extensions lies in bridging the Python packaging ecosystem, governed by PEP 517 and PEP 518, with external compiler toolchains.10 Modern Python relies on build backends to produce source distributions (SDists) and binary wheels.10 Integrating non-standard compilers, such as the Zig compiler or the.NET SDK ILCompiler, requires precise interception of the wheel construction lifecycle to ensure the compiled artifacts are correctly bundled into the final archive.10

### **2.1 Zig Build System Integration and Orchestration**

Zig is a general-purpose programming language and toolchain equipped with a highly capable, declarative build system executed via a build.zig script.14 This system replaces traditional Makefiles or CMake configurations, allowing developers to define build graphs, targets, and optimization levels entirely in Zig code.14 When integrating Zig into a Python packaging workflow, architects must evaluate whether to bridge Zig through an existing C/C++ backend or to invoke the Zig compiler directly from a native Python build script.17

#### **2.1.1 Bridging via Scikit-Build-Core**

scikit-build-core is a modern, PEP 517-compliant build backend engineered to connect CMake to Python packaging.12 It replaces the legacy, heavily patched setuptools configurations of the past, providing robust support for cross-compilation, dynamic metadata plugins, and strictly isolated build environments defined entirely within a pyproject.toml file.10  
For a Zig-based extension, scikit-build-core can be leveraged by configuring CMake to utilize Zig as the primary C and C++ compiler via the zig cc and zig c++ commands.4 The Zig toolchain acts as a seamless drop-in replacement for Clang, possessing the unique architectural advantage of bundling standard C libraries, such as glibc and musl, for dozens of target architectures.4 This enables effortless cross-compilation directly from the CMake interface without requiring the installation of complex cross-compilation SDKs on the host machine.4  
However, if the extension is written entirely in the Zig language rather than C/C++, integrating a native build.zig script into a CMake-driven scikit-build-core pipeline requires wrapping the build.zig invocation within a CMake add\_custom\_command or ExternalProject\_Add directive.21 This approach introduces an unnecessary layer of indirection. While scikit-build-core excels for projects maintaining substantial existing CMake infrastructure, utilizing it solely as a wrapper for zig build complicates the build graph and obscures the native caching mechanisms provided by the Zig compiler.15

#### **2.1.2 Direct Integration via Setuptools and Subprocessing**

For pure Zig projects, directly overriding the build\_ext command within the setuptools framework offers a highly cohesive and transparent architecture.23 Third-party plugins, most notably setuptools-zig, have pioneered this approach, allowing developers to specify build\_zig=True within the standard setup() function.8  
To build a shared library without relying on external plugins, the architectural blueprint involves subclassing setuptools.command.build\_ext.build\_ext.13 The custom class intercepts the C-extension build phase, maps Python's expected output paths, and spawns a subprocess invoking the Zig compiler directly.13

| Setuptools Execution Phase | Custom Override Implementation Logic |
| :---- | :---- |
| initialize\_options | Defines custom attributes, establishing the default optimization levels such as ReleaseFast, ReleaseSafe, or Debug based on the host environment.13 |
| finalize\_options | Resolves absolute directory paths, ensuring the build\_lib directory is identified so the compiled shared library can be deposited in the correct location for wheel inclusion.13 |
| build\_extension | Constructs the CLI subprocess array (e.g., \`\`) and executes it via the self.spawn() method.13 |

By bypassing scikit-build-core in favor of a customized setuptools extension, the pipeline ensures that Zig's native dependency manager and caching mechanisms remain the authoritative source of truth for the native binary's construction.13 This approach natively handles the generation of .so, .dll, or .dylib files and deposits them directly into the package structure, ensuring that the subsequent bdist\_wheel command seamlessly packages the native binary alongside the Python source files.27

### **2.2 C\# NativeAOT Compilation Matrix and Orchestration**

The introduction of.NET NativeAOT (Ahead-of-Time) compilation radically alters the deployment profile of C\# applications and libraries.29 Instead of compiling to Intermediate Language (IL) that relies on the CoreCLR Just-In-Time (JIT) compiler during execution, NativeAOT utilizes an ILCompiler to produce a fully self-contained, statically linked native executable or dynamically loaded shared library.31 This compilation paradigm enables C\# code to expose a standard C-ABI, making it fully consumable by Python via ctypes or cffi, while delivering instantaneous startup times and drastically reduced memory footprints.30

#### **2.2.1 MSBuild and the NativeAOT Configuration Profile**

To compile a C\# project as a native shared library, specific MSBuild properties must be explicitly declared within the .csproj file. The foundational property is \<PublishAot\>true\</PublishAot\>, which instructs the build system to route the assembly through the ILCompiler rather than the standard JIT output path.34 Concurrently, the property \<NativeLib\>Shared\</NativeLib\> must be defined to instruct the native linker to emit a dynamically loaded library rather than a standalone executable application.33  
Furthermore, to optimize the library for integration into a Python wheel, additional trimming properties should be leveraged to aggressively reduce the final binary size.35 By declaring \<PublishTrimmed\>true\</PublishTrimmed\> and \<InvariantGlobalization\>true\</InvariantGlobalization\>, the compiler executes static flow analysis to strip away unused.NET framework dependencies, reducing a typical standard library overhead from dozens of megabytes down to a highly portable artifact.35 Developers must strictly avoid runtime reflection and dynamic code generation within the C\# extension, as the NativeAOT compiler cannot resolve dynamic type discovery during the ahead-of-time compilation phase.29  
To expose C\# methods to the C-ABI, the \[UnmanagedCallersOnly(EntryPoint \= "method\_name")\] attribute is applied to static methods, signaling the ILCompiler to generate an unmanaged export symbol accessible to the Python interpreter.37 Frameworks such as DotWrap automate this process, generating both the C\# unmanaged exports and the corresponding Python ctypes wrappers.5

#### **2.2.2 Intercepting Setuptools for.NET Publish Commands**

Similar to the Zig integration strategy, packing a NativeAOT library requires overriding the setuptools build command to invoke the.NET CLI.26 The custom build\_ext class must orchestrate the dotnet publish command as a spawned subprocess, intercepting the standard C-compiler workflow.26  
The primary architectural complexity in this integration lies in translating Python's build environment parameters into.NET Runtime Identifiers (RIDs). The dotnet publish command demands an explicit \-r \<RID\> argument to resolve the appropriate target architecture and operating system combination for the ILCompiler.34 The Python ecosystem relies on PEP 425 platform compatibility tags (e.g., linux\_x86\_64, macosx\_arm64), which do not directly align with.NET RIDs.40  
The override script must intelligently query the host platform—or the cross-compilation environment variables injected by the CI system—and map them to the rigid.NET RID catalog.41

| Python Platform Tag Component | Corresponding.NET Runtime Identifier (RID) |
| :---- | :---- |
| linux\_x86\_64 | linux-x64 34 |
| linux\_aarch64 | linux-arm64 34 |
| macosx\_x86\_64 | osx-x64 42 |
| macosx\_arm64 | osx-arm64 42 |
| win\_amd64 | win-x64 32 |

The orchestrated subprocess command takes the definitive form: dotnet publish \-c Release \-r \<MAPPED\_RID\> /p:PublishAot=true \-o \<BUILD\_LIB\_PATH\>.30 The custom setuptools pipeline must then locate the resulting .so, .dll, or .dylib artifact within the output directory and programmatically copy it adjacent to the Python module source files before the final wheel packaging sequence concludes.26

## **3\. Continuous Integration and Cross-Platform Distribution**

Deploying native extensions to a diverse data science user base necessitates pre-compiling binary wheels for multiple operating systems and CPU architectures. Requiring end-users to possess the Zig compiler or the comprehensive.NET 8/9 SDK locally fundamentally violates the frictionless pip install paradigm.5 Therefore, Continuous Integration (CI) pipelines must build and upload these multi-platform wheels to the Python Package Index (PyPI) or a private repository.44

### **3.1 The Cibuildwheel Orchestration Lifecycle**

The industry-standard architectural tool for orchestrating cross-platform Python wheel builds is cibuildwheel.45 Executed within a CI provider such as GitHub Actions, cibuildwheel automates the creation of strictly isolated build environments, iterating over multiple Python versions (such as CPython 3.9 through 3.13, PyPy, and GraalPy) and sequentially invoking the PEP 517 build backend defined in the project's pyproject.toml.45  
For a native extension project, the GitHub Actions workflow defines a matrix strategy covering standard runners such as ubuntu-latest, windows-latest, macos-13 (Intel), and macos-14 (Apple Silicon).46 The pipeline utilizes the pypa/cibuildwheel GitHub action to initiate the build matrix, automatically aggregating the resulting wheels into an artifact repository for final deployment.48

#### **3.1.1 Environment Injection and Toolchain Provisioning**

cibuildwheel executes macOS and Windows builds directly on the CI runner host, meaning any global dependencies or compilers installed prior to execution are natively available to the Python build script.46 However, Linux builds occur inside highly controlled, isolated Docker containers (specifically manylinux or musllinux images) to guarantee strict glibc backward compatibility across a multitude of enterprise distributions.11  
Because these containers provide strictly minimal environments based on older operating systems (such as CentOS 7 for manylinux2014 or AlmaLinux 8 for manylinux\_2\_28), neither the Zig compiler nor the.NET SDK are present by default.11 To provision these required toolchains inside the container prior to the build phase, architects must utilize the CIBW\_BEFORE\_ALL configuration option.48  
This configuration parameter accepts shell commands that are executed inside the container environment immediately before the wheel building iteration begins.49 For a C\# NativeAOT pipeline, the CIBW\_BEFORE\_ALL\_LINUX directive must execute a bash sequence to securely download the.NET SDK tarball via curl, extract it to a persistent directory, and append the binary path to the environmental execution scope.50  
For a Zig-based extension, a parallel methodology is employed to download the pre-compiled Zig binary release.52 The installation step is remarkably lightweight, as Zig is entirely self-contained and avoids system-level dependency conflicts entirely.4

### **3.2 Cross-Compilation and Hardware Emulation Strategies**

Providing wheels for ARM64 architectures (such as Apple M-series chips and AWS Graviton processors) is critical for modern data science, as analytical workloads rapidly migrate to high-efficiency ARM hardware.42

#### **3.2.1 Linux ARM64 Emulation Constraints**

On GitHub Actions, compiling aarch64 Linux wheels typically requires hardware emulation if native ARM runners are unavailable or costly to configure. By integrating the docker/setup-qemu-action, cibuildwheel seamlessly routes aarch64 builds through QEMU.48  
However, NativeAOT compilation via QEMU emulation introduces severe performance degradation and occasional memory allocation faults due to the intense computational requirements of the ILCompiler.42 The process of analyzing the entire.NET assembly graph to generate static native code frequently exhausts emulated memory limits.53 Consequently, it is strongly advised to utilize native ARM64 GitHub Actions runners (e.g., ubuntu-24.04-arm) mapped within the CI matrix to execute the cibuildwheel process directly on bare metal or virtualized ARM infrastructure.11

#### **3.2.2 macOS Universal2 and Apple Silicon**

For macOS environments, cibuildwheel robustly supports cross-compilation. An Intel-based runner can compile arm64 wheels if the underlying toolchain supports cross-targeting.47 The C\# ILCompiler currently possesses limited support for cross-architecture NativeAOT compilation, inherently dependent on the presence of the host SDK.42 Thus, utilizing the macos-14 runner specifically for Apple Silicon and macos-13 for Intel x86\_64 prevents cross-compilation linker errors.46  
Zig natively excels at cross-compilation via the explicit \-Dtarget flag.4 If the build system extracts the target architecture from the ARCHFLAGS or CIBW\_ARCHS environment variables provided by cibuildwheel, the custom build\_ext script can effortlessly instruct zig build-lib to target aarch64-macos-none or x86\_64-windows-gnu directly from a standard Linux runner, drastically accelerating the CI workflow by centralizing compilation tasks.4

### **3.3 Glibc Compatibility and the Manylinux Standard**

The manylinux standard dictates that Linux binary distributions must link against an incredibly old version of glibc to ensure forward compatibility with enterprise distributions. The historical manylinux2014 standard guarantees compatibility with systems using glibc 2.17.55  
Zig handles this requirement transparently. Because it does not rely strictly on the host system's C library, it can target specific glibc versions directly via its target triple (e.g., x86\_64-linux-gnu.2.17).57 This guarantees that a Zig extension compiled on a modern Ubuntu runner will execute flawlessly on legacy Red Hat Enterprise Linux servers.57  
Conversely, C\# NativeAOT poses distinct challenges. The.NET ILCompiler relies on the host environment's linker and glibc headers. Compiling NativeAOT inside manylinux2014 has historically encountered linker assertions and missing symbols (e.g., mallinfo2 or advanced thread-local storage primitives).58 Therefore, NativeAOT extensions generally demand the more modern manylinux\_2\_28 image (based on AlmaLinux 8, glibc 2.28), consciously dropping support for end-of-life Linux distributions.11 The build system architect must configure pyproject.toml to explicitly declare this compatibility baseline:

Ini, TOML

\[tool.cibuildwheel\]  
manylinux-x86\_64-image \= "manylinux\_2\_28"  
manylinux-aarch64-image \= "manylinux\_2\_28"

### **3.4 Dynamic Loading Architecture and Repair Mechanics**

Once the native compiler generates the shared library, the Python wheel packaging process must manage absolute and relative dependencies embedded within the binary metadata, ensuring the target operating system's dynamic loader can resolve the extension at runtime.59  
When cibuildwheel finishes invoking the build backend, it automatically subjects the resulting wheel to a platform-specific repair tool: auditwheel for Linux, delocate for macOS, and delvewheel for Windows.45 These tools introspect the shared library to identify dependencies on non-standard external libraries. If an external dependency is identified, the repair tool copies the .so or .dylib into the wheel archive and rewrites the dynamic linking metadata of the primary extension to point to the newly bundled copy.62  
On Linux, auditwheel modifies the RPATH (Run-Time Search Path) or RUNPATH of the binary. It inserts a relative path utilizing the $ORIGIN variable, instructing the dynamic linker (ld.so) to search for dependencies relative to the location of the calling library.59  
Both Zig and NativeAOT inherently limit external dependencies, often resulting in binaries that only link against libc, libm, libpthread, and libdl.64 Because these are foundational system libraries permitted by the manylinux standard, auditwheel will analyze the Zig or NativeAOT binary, determine no prohibited external dependencies exist, assign the appropriate manylinux tag, and pass the wheel without modification.56  
For Windows, RPATH concepts do not exist.65 The Windows loader resolves DLLs using the system PATH, the application directory, or explicit paths passed to the loader.66 Since NativeAOT and Zig strongly encourage single-file monolithic shared libraries, complex dependency resolution is elegantly bypassed, resulting in clean, self-contained artifacts.32

## **4\. Safest Python-Side Module Initialization**

Once the fully self-contained wheel is deployed to the end-user's environment via pip install, the Python interpreter must successfully locate, load, and instantiate the native code. Hardcoding relative filesystem paths (e.g., ../lib/extension.so) creates highly fragile architectures that fracture when executed from varying virtual environments, zipped imports, or PyInstaller deployments.67

### **4.1 Locating the Compiled Binary Dynamically**

The optimal architectural pattern for dynamically locating the shared library leverages Python's modern resource loading APIs or explicit boundary calculations relative to the \_\_file\_\_ attribute of the executing script.69  
The library loader must natively account for platform-specific filename extensions. The ctypes.util.find\_library function is notoriously unreliable for localized package directories, meaning constructing the absolute path explicitly is required.60  
By ensuring the build\_ext step deposits the compiled .so, .dll, or .dylib directly into the package directory adjacent to the Python \_\_init\_\_.py file, the \_\_file\_\_ resolution guarantees an accurate discovery regardless of the virtual environment's topological depth.66 Additionally, the importlib.resources.files API introduced in Python 3.9 provides a strictly safer alternative to \_\_file\_\_ for discovering intra-package binary assets, smoothly accommodating scenarios where the package resides within a zipped archive or constrained execution environment.68  
When a reliable absolute path is resolved, the module executes a ctypes.CDLL() instantiation on Linux and macOS, or a ctypes.WinDLL() call on Windows if the native compiler enforces stdcall conventions rather than cdecl.70

### **4.2 Handling Windows DLL Search Paths**

In Python 3.8 and newer, the mechanism for locating Windows DLL dependencies tightened significantly for security purposes, ignoring the global PATH variable entirely.72 If a NativeAOT or Zig DLL depends on another bundled DLL, the standard LoadLibrary call will fail with a FileNotFoundError despite the DLL existing in the same directory.72  
To circumvent this, the Python module must explicitly call os.add\_dll\_directory(package\_dir) prior to loading the main extension.72 This securely amends the DLL search path strictly for the executing context, ensuring that internal dependencies resolve without polluting the global environment or requiring anti-patterns like modifying LD\_LIBRARY\_PATH on Unix systems.60

### **4.3 FFI Definitions and Calling Conventions**

To interact reliably with the loaded ctypes.CDLL object, the Python layer must strictly define the argument types (argtypes) and return type (restype) of the exposed C-ABI functions.3 Without explicit type declarations, ctypes defaults to assuming int returns, leading to catastrophic segmentation faults when receiving 64-bit pointers.73  
Because C\# NativeAOT mandates the use of \[UnmanagedCallersOnly(EntryPoint \= "modify\_categorical")\] 37, and Zig exposes functions via export fn modify\_categorical(...) 28, the resulting symbols adhere to the standard C calling conventions, providing a stable foundation for the ctypes wrapper.70

## **5\. The Dynamic Loading Architecture for Arrow In-Place Memory**

The crux of the analytical workflow requires the native library to modify a Pandas Categorical array in-place. Passing multi-dimensional array pointers natively between Python memory and native memory is historically fraught with serialization overhead, reference counting issues, and segmentation faults.1  
The implementation of the Apache Arrow C Data Interface revolutionizes this process. The interface permits zero-copy sharing of Arrow memory between Python data frames (Pandas, Polars, PyArrow) and independent compiled runtimes (Zig, NativeAOT).1

### **5.1 Arrow C Data Interface Data Structures**

The Arrow C Data Interface relies on two fundamental C structs to communicate memory layout and types: ArrowSchema and ArrowArray.1  
The ArrowSchema defines the format, indicating dictionary-encoded string categoricals, variable-length lists, or primitive types, alongside any relevant schema metadata.1 The ArrowArray structure acts as the core memory container, containing pointers to the exact length, null count, internal offsets, and the contiguous memory buffers (including the validity bitmap, offset array, and data array).1  
When the Zig or C\# native layer modifies the Pandas array, it accepts a pointer to the ArrowArray, decoding the structure and accessing the buffers double-pointer array directly. By writing directly to these buffers, memory is altered in-place with zero serialization latency, entirely bypassing the Python interpreter and the GIL.1

### **5.2 The PyCapsule Protocol and Safety Mechanisms**

Historically, exposing these C structures to Python involved passing raw integer representations of the void\* pointers via ctypes.9 However, raw pointers bypass Python's garbage collection. If an exception interrupts the Python execution context before the native memory is freed, the memory leaks permanently, compromising long-running data science workloads.76  
The modern standard dictates the use of the Arrow PyCapsule Interface, directly inspired by the DLPack specification.9 A PyCapsule is a standard Python C-API object designed specifically to hold an opaque void\* pointer and carry a strongly bound C-level destructor callback.9

#### **5.2.1 Constructing the PyCapsule at the Native Boundary**

To export data securely, the Zig or C\# native layer must not return an integer pointer. Instead, it must utilize the Python C-API to instantiate a PyCapsule. The architecture dictates that the native extension links against libpython (or uses ctypes.pythonapi from the Python side) to invoke PyCapsule\_New.9

1. **Allocation:** The native layer allocates an ArrowArray struct on the heap, populating it with the generated categorical data.1  
2. **Naming Convention:** The capsule must be instantiated with a strictly defined name constraint. For an ArrowArray, the name must be exactly "arrow\_array".9 This string acts as an embedded type-check, ensuring consumers do not accidentally cast a schema pointer into an array struct.9  
3. **Destructor Binding:** The PyCapsule\_New call binds a function pointer to a destructor.9 If the Python object wrapping the capsule is garbage-collected without the Arrow data being fully consumed by the target dataframe, the destructor automatically evaluates the ArrowArray-\>release callback.9 This ensures the native heap memory is cleanly deallocated, eliminating the memory leak risk entirely.79

| Struct Type | Required PyCapsule Name | Description |
| :---- | :---- | :---- |
| ArrowSchema | "arrow\_schema" | Describes the data types (e.g., dictionary types for Pandas categoricals).9 |
| ArrowArray | "arrow\_array" | Houses the exact memory buffer pointers holding the columnar data.9 |
| ArrowArrayStream | "arrow\_array\_stream" | Allows chunked, sequential iteration of datasets exceeding available RAM.9 |

#### **5.2.2 Consuming PyCapsules in Python**

On the Python side, the module structure intercepts the returned PyCapsule. Any modern data frame library compatible with the Arrow ecosystem (including Pandas 2.2+, Polars, and PyArrow) natively understands these PyCapsules through standard Dunder methods.76  
By defining a lightweight Python wrapper class that exposes the \_\_arrow\_c\_array\_\_ method, the native extension can yield objects that integrate flawlessly into the Python data science stack.76  
When a library like Polars or Narwhals receives this PyCapsule, it internally calls PyCapsule\_GetPointer(capsule, "arrow\_array") to validate the type name and extract the memory structure safely.9 It then assumes ownership of the memory, subsequently renaming the capsule or nullifying the release callback to prevent double-free corruption, and finally invoking the internal release callback once the Python runtime concludes operations on the dataframe.9  
This implementation shields the end-user entirely from the underlying mechanics of memory management, pointer casting, and cross-boundary FFI invocations.75 Data scientists only interact with Python native objects, calling familiar analytical functions, while the compiled extension securely mutates categorical arrays at the execution speed of the underlying Zig or C\# runtime.

## **6\. Strategic Synthesis**

Distributing natively compiled, memory-safe extensions within standard Python workflows demands a rigorously defined integration pipeline. By architecting a custom setuptools build command, the deployment framework effortlessly abstracts away the inherent complexities of the Zig compiler and the.NET ILCompiler, executing zig build-lib or dotnet publish as native subroutines fully integrated into the PEP 517 lifecycle.  
Continuous Integration orchestration via cibuildwheel, operating on GitHub Actions matrix runners, provides deterministic, cross-platform wheel generation. By utilizing CIBW\_BEFORE\_ALL within manylinux containers to inject non-standard toolchains, and carefully navigating glibc compatibility requirements by adopting the manylinux\_2\_28 standard for C\# NativeAOT, the pipeline produces pristine artifacts. These artifacts install universally via pip across Windows, macOS, and Linux without necessitating user-side compilation.  
At runtime, robust location strategies combined with the Arrow PyCapsule Interface establish a profoundly secure, zero-copy conduit between the Python runtime and the high-performance Zig or C\# core. This holistic architectural pattern eliminates traditional FFI serialization bottlenecks, safeguards against memory leakage, and ensures that sophisticated data science tooling can be deployed with unparalleled efficiency and stability.

#### **Works cited**

1. The Arrow C data interface — Apache Arrow v24.0.0, accessed on May 7, 2026, [https://arrow.apache.org/docs/format/CDataInterface.html](https://arrow.apache.org/docs/format/CDataInterface.html)  
2. Updating Extension Modules \- Python Free-Threading Guide, accessed on May 7, 2026, [https://py-free-threading.github.io/porting-extensions/](https://py-free-threading.github.io/porting-extensions/)  
3. Interfacing Python with C/C++ for Performance (2024), accessed on May 7, 2026, [https://www.paulnorvig.com/guides/interfacing-python-with-cc-for-performance.html](https://www.paulnorvig.com/guides/interfacing-python-with-cc-for-performance.html)  
4. Learning Zig and Zig Build by porting Piper's CMakeLists.txt \- Compile and Run, accessed on May 7, 2026, [https://compileandrun.com/zig-build-cargo-piper/](https://compileandrun.com/zig-build-cargo-piper/)  
5. Automatically generate a python package that wraps your .NET AOT project \- Reddit, accessed on May 7, 2026, [https://www.reddit.com/r/dotnet/comments/1mtm063/automatically\_generate\_a\_python\_package\_that/](https://www.reddit.com/r/dotnet/comments/1mtm063/automatically_generate_a_python_package_that/)  
6. How do I use scikit-build to compile an extension module as part of another setup.py, accessed on May 7, 2026, [https://stackoverflow.com/questions/57518795/how-do-i-use-scikit-build-to-compile-an-extension-module-as-part-of-another-setu](https://stackoverflow.com/questions/57518795/how-do-i-use-scikit-build-to-compile-an-extension-module-as-part-of-another-setu)  
7. Sharing libraries between wheels documentation \- Read the Docs, accessed on May 7, 2026, [https://native-lib-loader.readthedocs.io/en/latest/](https://native-lib-loader.readthedocs.io/en/latest/)  
8. setuptools-zig \- PyPI, accessed on May 7, 2026, [https://pypi.org/project/setuptools-zig/](https://pypi.org/project/setuptools-zig/)  
9. The Arrow PyCapsule Interface — Apache Arrow v24.0.0, accessed on May 7, 2026, [https://arrow.apache.org/docs/format/CDataInterface/PyCapsuleInterface.html](https://arrow.apache.org/docs/format/CDataInterface/PyCapsuleInterface.html)  
10. Build procedure \- scikit-build-core 0.12.2 documentation \- Read the Docs, accessed on May 7, 2026, [https://scikit-build-core.readthedocs.io/en/stable/guide/build.html](https://scikit-build-core.readthedocs.io/en/stable/guide/build.html)  
11. GitHub \- pypa/cibuildwheel: Build Python wheels for all the platforms with minimal configuration., accessed on May 7, 2026, [https://github.com/pypa/cibuildwheel](https://github.com/pypa/cibuildwheel)  
12. GitHub \- scikit-build/scikit-build-core: A next generation Python CMake adaptor and Python API for plugins, accessed on May 7, 2026, [https://github.com/scikit-build/scikit-build-core](https://github.com/scikit-build/scikit-build-core)  
13. Zig \+ Python Easy & Optimized \- Nicola Landro, accessed on May 7, 2026, [https://z-uo.medium.com/zig-python-easy-optimized-f64341625d04](https://z-uo.medium.com/zig-python-easy-optimized-f64341625d04)  
14. Zig Build \- Zig Guide, accessed on May 7, 2026, [https://zig.guide/build-system/zig-build/](https://zig.guide/build-system/zig-build/)  
15. Zig Build System \- Zig Programming Language, accessed on May 7, 2026, [https://ziglang.org/learn/build-system/](https://ziglang.org/learn/build-system/)  
16. Zig Build System Basics \- Media \- Ziggit, accessed on May 7, 2026, [https://ziggit.dev/t/zig-build-system-basics/10275](https://ziggit.dev/t/zig-build-system-basics/10275)  
17. writing Python modules in Zig \- Reddit, accessed on May 7, 2026, [https://www.reddit.com/r/Zig/comments/k2bv2j/writing\_python\_modules\_in\_zig/](https://www.reddit.com/r/Zig/comments/k2bv2j/writing_python_modules_in_zig/)  
18. Packaging Zig as Python packages \- Help \- Ziggit, accessed on May 7, 2026, [https://ziggit.dev/t/packaging-zig-as-python-packages/7084](https://ziggit.dev/t/packaging-zig-as-python-packages/7084)  
19. zig cc as a drop-in CC= replacement for Python extension builds · GitHub, accessed on May 7, 2026, [https://github.com/cemrehancavdar/zig-cc-python](https://github.com/cemrehancavdar/zig-cc-python)  
20. ziglang \- PyPI, accessed on May 7, 2026, [https://pypi.org/project/ziglang/](https://pypi.org/project/ziglang/)  
21. scikit-build-core/docs/guide/getting\_started.md at main \- GitHub, accessed on May 7, 2026, [https://github.com/scikit-build/scikit-build-core/blob/main/docs/guide/getting\_started.md?plain=true](https://github.com/scikit-build/scikit-build-core/blob/main/docs/guide/getting_started.md?plain=true)  
22. Welcome to scikit-build — scikit-build 0.1.dev50+g6c016fd91 documentation, accessed on May 7, 2026, [https://scikit-build.readthedocs.io/](https://scikit-build.readthedocs.io/)  
23. Building Extension Modules \- setuptools 82.0.1 documentation, accessed on May 7, 2026, [https://setuptools.pypa.io/en/latest/userguide/ext\_modules.html](https://setuptools.pypa.io/en/latest/userguide/ext_modules.html)  
24. Extending or Customizing Setuptools, accessed on May 7, 2026, [https://setuptools.pypa.io/en/latest/userguide/extension.html](https://setuptools.pypa.io/en/latest/userguide/extension.html)  
25. codelv/py.zig: Lightweight python bindings for zig \- GitHub, accessed on May 7, 2026, [https://github.com/codelv/py.zig](https://github.com/codelv/py.zig)  
26. python setuptools with many commands : r/learnpython \- Reddit, accessed on May 7, 2026, [https://www.reddit.com/r/learnpython/comments/14mvmbh/python\_setuptools\_with\_many\_commands/](https://www.reddit.com/r/learnpython/comments/14mvmbh/python_setuptools_with_many_commands/)  
27. Python setuptools/distutils custom build for the \`extra\` package with Makefile, accessed on May 7, 2026, [https://stackoverflow.com/questions/41169711/python-setuptools-distutils-custom-build-for-the-extra-package-with-makefile](https://stackoverflow.com/questions/41169711/python-setuptools-distutils-custom-build-for-the-extra-package-with-makefile)  
28. compile CPython extension written in Zig on Windows \- Stack Overflow, accessed on May 7, 2026, [https://stackoverflow.com/questions/77466479/compile-cpython-extension-written-in-zig-on-windows](https://stackoverflow.com/questions/77466479/compile-cpython-extension-written-in-zig-on-windows)  
29. .NET Native AOT Explained \- NDepend Blog, accessed on May 7, 2026, [https://blog.ndepend.com/net-native-aot-explained/](https://blog.ndepend.com/net-native-aot-explained/)  
30. How to Enable Native AOT in .NET 8: A Step-by-Step Guide with Performance Benchmark, accessed on May 7, 2026, [https://www.avidclan.com/blog/how-to-enable-native-aot-in-dot-net-8-a-step-by-step-guide-with-performance-benchmark/](https://www.avidclan.com/blog/how-to-enable-native-aot-in-dot-net-8-a-step-by-step-guide-with-performance-benchmark/)  
31. Native AOT Deployment Model in dotNet | by Funda Özmen | adessoTurkey \- Medium, accessed on May 7, 2026, [https://medium.com/adessoturkey/native-aot-deployment-model-in-dotnet-e2dd341cf2e0](https://medium.com/adessoturkey/native-aot-deployment-model-in-dotnet-e2dd341cf2e0)  
32. Mastering .NET Native AOT: Benefits and Examples | by Juan España \- Medium, accessed on May 7, 2026, [https://medium.com/bytehide/mastering-net-native-aot-benefits-and-examples-d41290e74ff8](https://medium.com/bytehide/mastering-net-native-aot-benefits-and-examples-d41290e74ff8)  
33. Using .NET Native AOT to build Windows WinAPI Dlls \- Rick Strahl's Web Log, accessed on May 7, 2026, [https://weblog.west-wind.com/posts/2026/Apr/28/Using-NET-Native-AOT-to-build-Windows-WinAPI-Dlls](https://weblog.west-wind.com/posts/2026/Apr/28/Using-NET-Native-AOT-to-build-Windows-WinAPI-Dlls)  
34. Native AOT deployment overview \- .NET | Microsoft Learn, accessed on May 7, 2026, [https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/)  
35. Native AOT in .NET: Smaller, Faster Apps for the Real World | by Faisal Iqbal \- Medium, accessed on May 7, 2026, [https://medium.com/@faysalwrites/native-aot-in-net-smaller-faster-apps-for-the-real-world-610caa77a8a4](https://medium.com/@faysalwrites/native-aot-in-net-smaller-faster-apps-for-the-real-world-610caa77a8a4)  
36. Demystifying .NET Native AOT: An Engineer's Implementation Guide \- Medium, accessed on May 7, 2026, [https://medium.com/codex/demystifying-net-native-aot-an-engineers-implementation-guide-cc204c713113](https://medium.com/codex/demystifying-net-native-aot-an-engineers-implementation-guide-cc204c713113)  
37. Create and consume custom frameworks for iOS-like platforms \- .NET \- Microsoft Learn, accessed on May 7, 2026, [https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/ios-like-platforms/creating-and-consuming-custom-frameworks](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/ios-like-platforms/creating-and-consuming-custom-frameworks)  
38. Automatically generate a python package that wraps your .NET AOT project \- Reddit, accessed on May 7, 2026, [https://www.reddit.com/r/csharp/comments/1mto3jv/automatically\_generate\_a\_python\_package\_that/](https://www.reddit.com/r/csharp/comments/1mto3jv/automatically_generate_a_python_package_that/)  
39. Tutorial: Publish an ASP.NET Core app using Native AOT | Microsoft Learn, accessed on May 7, 2026, [https://learn.microsoft.com/en-us/aspnet/core/fundamentals/aot/native-aot-tutorial?view=aspnetcore-10.0](https://learn.microsoft.com/en-us/aspnet/core/fundamentals/aot/native-aot-tutorial?view=aspnetcore-10.0)  
40. Platform compatibility tags \- Python Packaging User Guide, accessed on May 7, 2026, [https://packaging.python.org/specifications/platform-compatibility-tags/](https://packaging.python.org/specifications/platform-compatibility-tags/)  
41. NET Runtime Identifier (RID) catalog \- Microsoft Learn, accessed on May 7, 2026, [https://learn.microsoft.com/en-us/dotnet/core/rid-catalog](https://learn.microsoft.com/en-us/dotnet/core/rid-catalog)  
42. Cross-compilation \- .NET | Microsoft Learn, accessed on May 7, 2026, [https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/cross-compile](https://learn.microsoft.com/en-us/dotnet/core/deploying/native-aot/cross-compile)  
43. Publish .NET 8 service as native (AOT) inside docker \- Stack Overflow, accessed on May 7, 2026, [https://stackoverflow.com/questions/77781280/publish-net-8-service-as-native-aot-inside-docker](https://stackoverflow.com/questions/77781280/publish-net-8-service-as-native-aot-inside-docker)  
44. cibuildwheel/examples/github-deploy.yml at main, accessed on May 7, 2026, [https://github.com/pypa/cibuildwheel/blob/main/examples/github-deploy.yml](https://github.com/pypa/cibuildwheel/blob/main/examples/github-deploy.yml)  
45. cibuildwheel, accessed on May 7, 2026, [https://cibuildwheel.pypa.io/](https://cibuildwheel.pypa.io/)  
46. Platforms \- cibuildwheel, accessed on May 7, 2026, [https://cibuildwheel.pypa.io/en/stable/platforms/](https://cibuildwheel.pypa.io/en/stable/platforms/)  
47. Setup \- cibuildwheel, accessed on May 7, 2026, [https://cibuildwheel.pypa.io/en/v2.22.0/setup/](https://cibuildwheel.pypa.io/en/v2.22.0/setup/)  
48. Tips and tricks \- cibuildwheel, accessed on May 7, 2026, [https://cibuildwheel.pypa.io/en/stable/faq/](https://cibuildwheel.pypa.io/en/stable/faq/)  
49. Options \- cibuildwheel, accessed on May 7, 2026, [https://cibuildwheel.pypa.io/en/stable/options/](https://cibuildwheel.pypa.io/en/stable/options/)  
50. Install .NET on Linux by using an install script or by extracting binaries \- Microsoft Learn, accessed on May 7, 2026, [https://learn.microsoft.com/en-us/dotnet/core/install/linux-scripted-manual](https://learn.microsoft.com/en-us/dotnet/core/install/linux-scripted-manual)  
51. Installation | zig.guide, accessed on May 7, 2026, [https://zig.guide/getting-started/installation/](https://zig.guide/getting-started/installation/)  
52. GitHub \- marler8997/zigbuild: Tools and resources to build/update the zig compiler, accessed on May 7, 2026, [https://github.com/marler8997/zigbuild](https://github.com/marler8997/zigbuild)  
53. Trying to statically link libc with NativeAOT causes a fatal crash in the linker · Issue \#100230 · dotnet/runtime \- GitHub, accessed on May 7, 2026, [https://github.com/dotnet/runtime/issues/100230](https://github.com/dotnet/runtime/issues/100230)  
54. MichalStrehovsky/PublishAotCross: NuGet package to help you cross-compile Native AOT to different OSes/architectures \- GitHub, accessed on May 7, 2026, [https://github.com/MichalStrehovsky/PublishAotCross](https://github.com/MichalStrehovsky/PublishAotCross)  
55. pypa/manylinux: Python wheels that work on any linux (almost) \- GitHub, accessed on May 7, 2026, [https://github.com/pypa/manylinux](https://github.com/pypa/manylinux)  
56. Distribution \- Maturin User Guide, accessed on May 7, 2026, [https://www.maturin.rs/distribution.html](https://www.maturin.rs/distribution.html)  
57. Theory of "target-triple" and how to run Zig on "POSIX-compliant" system \- Explain \- Ziggit, accessed on May 7, 2026, [https://ziggit.dev/t/theory-of-target-triple-and-how-to-run-zig-on-posix-compliant-system/12411](https://ziggit.dev/t/theory-of-target-triple-and-how-to-run-zig-on-posix-compliant-system/12411)  
58. How to use \`manylinux\_2\_34\`? · pypa cibuildwheel · Discussion \#2129 \- GitHub, accessed on May 7, 2026, [https://github.com/pypa/cibuildwheel/discussions/2129](https://github.com/pypa/cibuildwheel/discussions/2129)  
59. Wheel depending on shared library from another wheel \- Packaging \- Python Discussions, accessed on May 7, 2026, [https://discuss.python.org/t/wheel-depending-on-shared-library-from-another-wheel/26456](https://discuss.python.org/t/wheel-depending-on-shared-library-from-another-wheel/26456)  
60. Packaging C/CPP libraries as wheels \- Python discussion forum, accessed on May 7, 2026, [https://discuss.python.org/t/packaging-c-cpp-libraries-as-wheels/90183](https://discuss.python.org/t/packaging-c-cpp-libraries-as-wheels/90183)  
61. Python wheels manylinux build · Actions · GitHub Marketplace, accessed on May 7, 2026, [https://github.com/marketplace/actions/python-wheels-manylinux-build](https://github.com/marketplace/actions/python-wheels-manylinux-build)  
62. How to include external library with python wheel package \- Stack Overflow, accessed on May 7, 2026, [https://stackoverflow.com/questions/23916186/how-to-include-external-library-with-python-wheel-package](https://stackoverflow.com/questions/23916186/how-to-include-external-library-with-python-wheel-package)  
63. What is the right way to ship dynamic library \*.so with python package? \- Stack Overflow, accessed on May 7, 2026, [https://stackoverflow.com/questions/68664839/what-is-the-right-way-to-ship-dynamic-library-so-with-python-package](https://stackoverflow.com/questions/68664839/what-is-the-right-way-to-ship-dynamic-library-so-with-python-package)  
64. .NET 7 introduces Native AOT | Hacker News, accessed on May 7, 2026, [https://news.ycombinator.com/item?id=31431387](https://news.ycombinator.com/item?id=31431387)  
65. Using shared libraries \- meson-python, accessed on May 7, 2026, [https://mesonbuild.com/meson-python/how-to-guides/shared-libraries.html](https://mesonbuild.com/meson-python/how-to-guides/shared-libraries.html)  
66. Native dependencies in other wheels \-- how I do it, but maybe we can standardize something? \- Packaging \- Python Discussions, accessed on May 7, 2026, [https://discuss.python.org/t/native-dependencies-in-other-wheels-how-i-do-it-but-maybe-we-can-standardize-something/23913](https://discuss.python.org/t/native-dependencies-in-other-wheels-how-i-do-it-but-maybe-we-can-standardize-something/23913)  
67. Python setuptools build c library, access via cdll.LoadLibrary \- Arch Linux Forums, accessed on May 7, 2026, [https://bbs.archlinux.org/viewtopic.php?id=268884](https://bbs.archlinux.org/viewtopic.php?id=268884)  
68. importlib.resources – Package resource reading, opening and access — Python 3.14.5rc1 documentation, accessed on May 7, 2026, [https://docs.python.org/3/library/importlib.resources.html](https://docs.python.org/3/library/importlib.resources.html)  
69. Python ctypes: loading DLL from from a relative path \- Stack Overflow, accessed on May 7, 2026, [https://stackoverflow.com/questions/2980479/python-ctypes-loading-dll-from-from-a-relative-path](https://stackoverflow.com/questions/2980479/python-ctypes-loading-dll-from-from-a-relative-path)  
70. ctypes — A foreign function library for Python — Python 3.14.5rc1 documentation, accessed on May 7, 2026, [https://docs.python.org/3/library/ctypes.html](https://docs.python.org/3/library/ctypes.html)  
71. Extending Python With C Libraries and the “ctypes” Module – dbader.org, accessed on May 7, 2026, [https://dbader.org/blog/python-ctypes-tutorial](https://dbader.org/blog/python-ctypes-tutorial)  
72. Python Ctypes for Loading and Calling Shared Libraries \- DEV Community, accessed on May 7, 2026, [https://dev.to/yushulx/python-ctypes-for-loading-and-calling-shared-libraries-49n7](https://dev.to/yushulx/python-ctypes-for-loading-and-calling-shared-libraries-49n7)  
73. C Class Instance from Void Pointer using Ctypes \- Stack Overflow, accessed on May 7, 2026, [https://stackoverflow.com/questions/19389124/c-class-instance-from-void-pointer-using-ctypes](https://stackoverflow.com/questions/19389124/c-class-instance-from-void-pointer-using-ctypes)  
74. Python C Extension Exposing a Capsule to ctypes in order to use third party C code, accessed on May 7, 2026, [https://stackoverflow.com/questions/59887319/python-c-extension-exposing-a-capsule-to-ctypes-in-order-to-use-third-party-c-co](https://stackoverflow.com/questions/59887319/python-c-extension-exposing-a-capsule-to-ctypes-in-order-to-use-third-party-c-co)  
75. Leveraging the Arrow C Data Interface \- Will Ayd | Personal Blog, accessed on May 7, 2026, [https://willayd.com/leveraging-the-arrow-c-data-interface.html](https://willayd.com/leveraging-the-arrow-c-data-interface.html)  
76. Universal dataframe support with the Arrow PyCapsule Interface \+ Narwhals | Labs, accessed on May 7, 2026, [https://labs.quansight.org/blog/narwhals-pycapsule](https://labs.quansight.org/blog/narwhals-pycapsule)  
77. \[Python\] Add Python protocol for the Arrow C (Data/Stream) Interface \#35531 \- GitHub, accessed on May 7, 2026, [https://github.com/apache/arrow/issues/35531](https://github.com/apache/arrow/issues/35531)  
78. Capsules — Python 3.14.4 documentation, accessed on May 7, 2026, [https://docs.python.org/3/c-api/capsule.html](https://docs.python.org/3/c-api/capsule.html)  
79. \[Python\] Use PyCapsule for communicating C Data Interface pointers at the Python level · Issue \#34031 · apache/arrow \- GitHub, accessed on May 7, 2026, [https://github.com/apache/arrow/issues/34031](https://github.com/apache/arrow/issues/34031)