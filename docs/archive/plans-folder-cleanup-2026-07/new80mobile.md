# **Engineering Directives for Agent-Driven Mobile Development: React Native, Expo SDK 55, and FastAPI Architectures**

## **1\. Executive Summary**

The convergence of artificial intelligence coding agents and mobile application development necessitates highly deterministic, low-maintenance architectural frameworks. For a solo developer operating within a restricted allocation of approximately fifty hours per week, the technology stack must prioritize durability, minimal operational overhead, and long-term stability over transient industry trends. The analysis indicates that AI coding agents frequently struggle with the nuances of mobile development, particularly the divergence between web DOM paradigms and native mobile hierarchies, the complexities of platform-specific threading, and the historical fragmentation of the React Native ecosystem. To mitigate these failure modes within the Fabrik platform, a rigidly defined architectural baseline is required.

The mandated foundation is Expo SDK 55, utilizing the managed workflow exclusively. Bare workflow ejects are strictly prohibited unless a native module explicitly lacks an Expo config plugin, as managing native iOS and Android build files introduces unsustainable maintenance overhead for a solo operator. Expo SDK 55 entirely deprecates the Legacy Architecture; the React Native New Architecture, which relies on the Fabric renderer and the JavaScript Interface (JSI), is permanently enabled and cannot be disabled.1 This structural shift eliminates the asynchronous JSON bridge, allowing synchronous execution between JavaScript and native threads, thereby fundamentally altering performance optimization strategies and rendering many historical React Native tutorials obsolete. Agents trained on pre-2024 data frequently hallucinate solutions involving the legacy asynchronous JSON bridge, attempting to manually batch bridge traversals or utilizing deprecated libraries that rely on it.3

Regarding the presentation and styling layer, React Native's native StyleSheet API is enforced as the default styling paradigm. The utility-first library NativeWind, which ports Tailwind CSS to React Native, is explicitly rejected as a default. Recent benchmarks indicate that NativeWind v4 introduces severe performance regressions, rendering elements significantly slower than raw StyleSheet due to the runtime overhead of calculating utility classes across the mobile bridge.4 For applications requiring complex design tokens and adaptive theming, Unistyles is the only approved third-party styling abstraction. Unistyles operates via a C++ core directly through JSI, updating styles synchronously without triggering React component re-renders, offering performance parity with raw StyleSheet.6

The state management architecture dictates a strict delineation between global user interface state and asynchronous server state. Zustand is designated as the primary global state manager for client-side UI state. It provides a minimalistic, store-based API that avoids the boilerplate of Redux and the contextual re-render cascades inherent in native React Context.8 Jotai, while offering an elegant atomic model, introduces a steeper learning curve and fragmental state tracking that is less predictable for a solo developer requiring low-maintenance architectures.8 For server state, React Query (TanStack Query) is mandated, providing robust caching, deduplication, and optimistic update mechanisms that integrate seamlessly with the FastAPI backend.

Local data persistence relies entirely on MMKV as the default key-value storage engine. Engineered to operate synchronously via memory-mapped files, it outperforms the legacy AsyncStorage by a factor of thirty.11 AsyncStorage is formally banned from the architecture due to its asynchronous latency and artificial storage limits.12 However, because MMKV operates synchronously on the JavaScript thread, it cannot handle complex, multi-layered relational data without risking dropped user interface frames. For offline-first relational data requiring complex querying, expo-sqlite paired with Drizzle ORM is the only permissible alternative.12

### **Architectural Directives and System Mechanics**

The transition to Expo Router v7 represents a paradigm shift in how navigation state is handled within the application. Built on top of React Navigation v7, the router utilizes useSyncExternalStore for navigation state, isolating screen re-renders and resolving the cascading render issues prevalent in version 6\.14 This ensures that navigating to a deeply nested child screen does not force the entire parent tab navigator to recalculate its render tree. Expo Router also natively handles deep linking, converting URL schemes directly into file-system routes.15 However, custom URL schemes possess critical limitations, including the inability to route users to the App Store if the application is uninstalled, alongside security vulnerabilities related to link hijacking.16 Therefore, the architectural standard mandates the use of Universal Links for iOS and App Links for Android, configured strictly via the associatedDomains and intentFilters arrays within the app.json file.17

Component structure and folder layouts must adhere strictly to the conventions established by Expo Router. The SDK 55 default template shifts application logic into a /src/app directory to separate routing from configuration files.2 AI agents must be instructed to maintain this separation, placing reusable UI components in /src/components and state management logic in /src/store. When addressing platform-specific rendering anomalies, agents must utilize the Platform.select() method or the Platform.OS constant, ensuring that safe area insets are dynamically calculated via useSafeAreaInsets rather than applying hardcoded padding values.

Performance optimization within list rendering requires uncompromising adherence to modern standards. The standard FlatList component destroys and recreates native views as they scroll off-screen, leading to memory bloat and blank cells during rapid scrolling. The rule pack strictly mandates the use of Shopify's FlashList for any list exceeding twenty items. FlashList implements native view recycling, re-using existing native views to maintain a steady sixty frames per second.18 With the release of FlashList v2, the library relies on UI thread corrections in native code, alleviating the developer from manually calculating estimated item sizes in most scenarios.19 Memory optimization also extends to image rendering; the native \<Image\> component must be entirely replaced by expo-image, which provides aggressive disk and memory caching alongside WebP support.

Data ingestion and form handling introduce significant complexity when managed manually. To ensure durability, all forms must be constructed using react-hook-form coupled with zod for schema validation. This paradigm utilizes uncontrolled components, preventing the entire form from re-rendering upon every keystroke, a common performance bottleneck in React Native applications. The zod schema must precisely mirror the Pydantic schemas defined in the FastAPI backend, ensuring perfect type alignment across the network boundary.

Push notification implementation requires explicit awareness of Expo's architectural constraints. As of SDK 55, push notifications are entirely disabled within the Expo Go client.20 Developers and AI agents must utilize EAS Development Builds to test remote payloads. The configuration of push notifications requires meticulous handling of native permissions configured within the app.json.21 Agents must wrap the token generation sequence in an explicit permission request block, falling back gracefully if the user denies access.22

Over-The-Air (OTA) updates are a critical operational lever for the solo developer, but they require careful orchestration. Expo SDK 55 introduces an opt-in feature for Hermes bytecode diffing via EAS Update.23 Historically, OTA updates required the client device to download the entire JavaScript bundle. The implementation of the bsdiff algorithm allows EAS Update to serve binary patches, reducing download sizes by approximately seventy-five percent.23 Agents must configure this in the app.json via the enableBsdiffPatchSupport flag.23 However, OTA updates are strictly limited to JavaScript and asset modifications; agents must never attempt to push an OTA update if the underlying native code has been altered.

The backend infrastructure requires a highly optimized deployment strategy tailored for an ARM64 Ubuntu Virtual Private Server orchestrated by Coolify. The FastAPI application must be containerized using a strictly defined Dockerfile. AI agents frequently hallucinate python:alpine as the base image to reduce container size. In an ARM64 Python environment, this is a catastrophic anti-pattern.24 Alpine Linux utilizes the musl C standard library instead of glibc. Many Python data science and cryptography packages do not provide pre-compiled wheels for musl on ARM64.24 This forces the Docker build process to compile these packages from source C code, extending deployment times drastically and frequently resulting in compilation failures.24 The absolute standard for the Dockerfile is FROM python:3.12-slim-bookworm, ensuring compatibility with pre-compiled ARM64 manylinux wheels.25

| Infrastructure Component | Approved Standard | Rejected Alternative | Rationale |
| :---- | :---- | :---- | :---- |
| **Docker Base Image** | python:3.12-slim-bookworm | python:alpine | Avoids musl libc compilation failures on ARM64 architectures. |
| **Deployment Orchestration** | Coolify (Docker Compose) | Manual Systemd | Provides automated SSL termination and seamless GitHub integration. |
| **WebSocket Protocol** | Raw WebSockets (fastapi.WebSocket) | Server-Sent Events (SSE) | SSE is unidirectional and unsuitable for real-time mobile tracking. |

FastAPI is fundamentally stateless, requiring explicit architectural patterns to support real-time features such as live tracking or chat. WebSockets must be utilized, as Server-Sent Events (SSE) only support unidirectional communication from the server to the client.27 AI agents often implement basic, unmanaged WebSocket endpoints that leak memory when mobile clients disconnect abruptly. A robust Connection Manager class is required to store active connections, handle explicit disconnect events, and provide broadcast capabilities across specific rooms.28 The React Native client must simultaneously implement exponential backoff reconnection logic to recover from mobile operating system backgrounding events.

Testing paradigms for the solo developer must prioritize high-leverage automation over exhaustive unit coverage. While Jest and the React Native Testing Library remain the standard for pure logical functions, end-to-end testing provides the highest confidence for deployment. Traditional frameworks like Detox or Appium require complex native build configurations and are notoriously flaky due to asynchronous bridge delays. Maestro is the mandated end-to-end framework. It operates externally to the application, utilizing declarative YAML flows to interact directly with the accessibility tree.29 Maestro automatically handles implicit waits for network requests and animations, drastically reducing flakiness.30 It integrates natively with Expo Application Services via the eas-build-on-success hook, allowing tests to execute automatically in Maestro Cloud upon successful binary compilation.31

Finally, the enforcement of TypeScript strictness is non-negotiable. React Native 0.80 introduced a Strict TypeScript API, providing stronger and more futureproof type accuracy.33 By extending @react-native/typescript-config, the compiler resolves types from the generated source code rather than manually maintained declaration files.33 AI agents must be instructed to never utilize the any type, relying instead on interface declarations, discriminated unions, and unknown for runtime boundary parsing.34 This strictness acts as the first automated gate against agent hallucinations, ensuring that invalid component props or non-existent native methods fail at the compilation step before reaching the continuous integration pipeline.

## **2\. Canonical Rules for the MOBILE\_UI Rule Pack**

The following rules dictate the operational boundaries for AI coding agents interacting with the Fabrik platform. These rules are categorized by enforcement priority to ensure that critical architectural constraints are never violated, while allowing flexibility in domain-specific implementations.

**Must Enforce Always (Architectural Fundamentals):**

* Assume the Expo SDK 55 Managed Workflow exclusively; never execute npx expo eject or generate manual modifications to native android/ and ios/ directory files.35
* React Native New Architecture (Fabric and JSI) is permanently enabled; never attempt to disable it via newArchEnabled=false or utilize legacy bridge-dependent modules.1
* Web DOM elements (\<div\>, \<span\>, \<a\>, \<p\>) are strictly prohibited; utilize only React Native primitives (\<View\>, \<Text\>, \<Pressable\>).36
* FastAPI Docker deployments on ARM64 must utilize python:3.12-slim-bookworm; the alpine base image is permanently banned to prevent musl compilation failures.24
* Navigation must exclusively utilize Expo Router v7 file-based routing; do not instantiate manual NavigationContainer components.15
* Global user interface state must be managed via Zustand; Redux and standalone React Context providers for high-frequency state are banned.8
* Asynchronous server state and API interactions must be managed exclusively via TanStack React Query.
* Local key-value persistence must utilize react-native-mmkv; the AsyncStorage API is permanently banned due to asynchronous bridge latency.11
* Strict TypeScript is mandatory via @react-native/typescript-config; the use of the any type will fail continuous integration checks.33
* Push notification implementations must wrap token requests in explicit native permission request blocks configured via app.json plugins.21

**Nice to Have (Performance and Optimization):**

* List rendering for arrays exceeding twenty items should utilize @shopify/flash-list to enable native view recycling.18
* Image assets should utilize expo-image rather than the native \<Image\> component to leverage disk caching and WebP decoding.
* Forms should utilize react-hook-form paired with zod validation to prevent unnecessary component re-renders during text input.
* Over-the-air updates via EAS should configure enableBsdiffPatchSupport: true in the app.json to reduce payload sizes via bytecode diffing.23
* WebSocket clients in React Native should implement exponential backoff algorithms to handle cellular network disconnection and backgrounding events.
* End-to-end tests should be written in Maestro YAML format targeting testID attributes, stored in the .maestro/ directory.37

**Human Decision Only (Context-Dependent Architecture):**

* The transition from MMKV to expo-sqlite with Drizzle ORM is reserved only for complex relational data requiring offline search capabilities.12
* The adoption of react-native-unistyles over raw StyleSheet is reserved for applications requiring highly complex, cross-platform design token systems.7
* The implementation of Universal Links (iOS) and App Links (Android) over custom URL schemes requires DNS verification and domain ownership configuration.17

## **3\. Anti-Patterns and Banned Patterns Specific to React Native and Expo**

Artificial intelligence coding agents, largely trained on vast repositories of web development data, frequently introduce catastrophic anti-patterns when deployed within a React Native context. The most pervasive of these is DOM hallucination. Agents will often attempt to construct layouts using \<div\>, \<span\>, or \<ul\> tags, and apply standard CSS properties such as hover or media queries directly to inline style objects.36 Within the React Native runtime, these elements do not exist, resulting in immediate compilation failures. All views must be constructed using native primitives imported directly from the react-native package.

A similarly critical failure mode involves the misunderstanding of the Expo Managed Workflow boundaries. Agents attempting to install third-party native modules will frequently output instructions to execute pod install within the ios/ directory or manually modify the MainApplication.java file. In an Expo Managed Workflow, these directories are generated ephemerally during the continuous integration process via Prebuild.38 Any manual modifications are overwritten and lost. Native dependencies must exclusively utilize Expo Config Plugins defined within the app.json file. If an agent suggests altering a native file directly, the output must be rejected.

The deprecation of the React Native asynchronous bridge in favor of the New Architecture introduces severe incompatibility issues with legacy libraries. Agents will often suggest the installation of @react-native-community/async-storage for local data persistence. This library relies entirely on the deprecated bridge, introducing severe performance bottlenecks and artificial storage limitations.13 The Fabrik architecture explicitly bans AsyncStorage in favor of react-native-mmkv, which leverages the JavaScript Interface (JSI) for synchronous, memory-mapped operations.11 Furthermore, because MMKV is a native module, it is fundamentally incompatible with the Expo Go application. Agents must never suggest testing the application within Expo Go; all execution must occur within an EAS Development Build.39

In the realm of styling, utility-first CSS frameworks present a significant risk. Agents trained on modern web stacks will frequently attempt to install NativeWind or Tailwind CSS. While NativeWind v4 provides a familiar developer experience, benchmarks indicate a critical performance degradation, with render times up to 400% slower than native StyleSheet implementations.4 The overhead of calculating utility classes across the mobile interface violates the performance constraints of the platform. Therefore, NativeWind is permanently banned.

On the infrastructure side, the deployment of the FastAPI backend to an ARM64 Ubuntu Virtual Private Server introduces specific Docker anti-patterns. Agents obsessed with minimizing container image sizes will consistently suggest FROM python:alpine. Alpine Linux utilizes the musl C standard library. When installing Python packages that rely on C-extensions (such as cryptography or database drivers), the absence of pre-compiled musl wheels for ARM64 forces the container to compile the extensions from source code.24 This results in massive build times and cryptic compilation failures. The container must explicitly utilize Debian-based slim images, specifically python:3.12-slim-bookworm, to ensure access to glibc compiled manylinux wheels.26

| Banned Anti-Pattern | Manifestation | Required Resolution |
| :---- | :---- | :---- |
| **DOM Hallucination** | \<div\>, \<span\>, onClick events. | Use \<View\>, \<Text\>, onPress events. |
| **Native Modification** | Manual edits to Podfile or build.gradle. | Use Expo Config Plugins in app.json. |
| **Legacy Storage** | @react-native-async-storage/async-storage | Use react-native-mmkv via JSI. |
| **Utility Styling** | nativewind or twrnc libraries. | Use React Native StyleSheet. |
| **Alpine Docker** | FROM python:alpine on ARM64 hosts. | Use FROM python:3.12-slim-bookworm. |

## **4\. Execution Handoff Enforcements**

To constrain the behavior of AI coding agents before they begin generating code, a strict execution handoff protocol must be enforced via the prompt context. This protocol acts as a cognitive grounding mechanism, forcing the agent to explicitly acknowledge the architectural boundaries of the Fabrik platform.

First, the agent must execute a state alignment verification. Before writing any data-fetching or state-mutation logic, the agent must declare whether the feature utilizes local user interface state or remote server state. If the state is local, the agent must acknowledge that it will utilize Zustand. If the state relies on the FastAPI backend, the agent must acknowledge that it will utilize TanStack React Query. This prevents the agent from hallucinating monolithic Redux implementations or unnecessarily passing state through deeply nested React Context providers.

Second, the agent must undergo type rigidity confirmation. The agent must explicitly acknowledge that it is operating within the React Native 0.80+ Strict TypeScript API environment.33 The agent must state that it will not utilize the any type under any circumstances, and that all component props will be strictly defined via exported interfaces. This ensures that the generated code aligns with the @react-native/typescript-config rules enforced by the continuous integration pipeline.40

Third, the agent must verify platform safety checks. Because the application targets both iOS and Android, the agent must acknowledge that UI elements interacting with the device edges will utilize useSafeAreaInsets from react-native-safe-area-context.7 Furthermore, the agent must state that any hardware-specific implementations (such as shadows or keyboard avoiding views) will be wrapped in Platform.select() blocks to prevent inconsistent rendering across operating systems.

Finally, the agent must conduct a file context audit. Before creating a new atomic component (such as a button or text input), the agent must scan the /src/components directory to confirm whether a reusable component already exists. This prevents the codebase from fragmenting into dozens of slightly varying button components, a common side effect of agent-driven development.

## **5\. Automated Checks for final\_gate.py**

To guarantee that compromised or hallucinated agent output never reaches the production branch, a Python-based continuous integration gate (final\_gate.py) must be executed against all proposed file modifications. This script utilizes Abstract Syntax Tree (AST) parsing and regular expressions to enforce the architectural boundaries deterministically.

The first automated check is the DOM Regex Scanner. The script reads all modified .tsx files and executes a regular expression search designed to catch web primitives: re.search(r'\<(div|span|p|a|ul|li)\\b', file\_content). If this regex triggers a match, the build is immediately failed with a descriptive error reminding the agent that it is operating in a React Native environment, not a web browser.41

The second check enforces the Package Banlist. The script parses the package.json file to inspect the dependency arrays. If the keys "nativewind", "@react-native-community/async-storage", "redux", or "@react-navigation/native" (because Expo Router must be used instead) are detected, the build is terminated. This ensures that deprecated or poorly performing libraries cannot be sneaked into the architecture by an overly eager AI agent.

The third check involves Dockerfile Architecture Validation. The script parses the Dockerfile located in the backend directory. It examines the FROM instruction to ensure compliance with the ARM64 requirements. If the instruction contains the substring alpine, the build fails immediately, enforcing the requirement for Debian-based slim-bookworm images to prevent musl libc compilation errors.24

The fourth check utilizes AST parsing to ensure proper WebSocket Cleanup. When a .tsx file utilizes the useEffect hook to instantiate a WebSocket connection to the FastAPI backend, the script parses the syntax tree to verify that a cleanup function is returned. It searches for return () \=\> ws.close() or equivalent logic. If the cleanup function is missing, the build fails, preventing the AI agent from introducing severe memory leaks into the mobile client.

Finally, the script executes a Strict Type Compilation check. It runs npx tsc \--noEmit against the codebase. The build must fail on any TypeScript errors, enforcing the Strict API conditions and ensuring that no any types or implicit variable declarations have bypassed the agent's internal logic.33

## **6\. What belongs in AGENTS.md**

The AGENTS.md file serves as the permanent system prompt, anchored to the root of the repository. It dictates the macro-behavior of all agents entering the workspace, providing them with the necessary context to navigate the specific constraints of the Fabrik platform without requiring exhaustive prompting from the developer.42

# **AGENTS.md: Fabrik React Native Architecture**

## **Core Context**

* **Framework:** React Native 0.83+, Expo SDK 55\.
* **Workflow:** Managed Workflow EXCLUSIVELY. Never suggest npx expo eject.
* **Architecture:** New Architecture (Fabric/JSI) is permanently enabled.
* **Language:** TypeScript exclusively. Strict Mode is enforced via @react-native/typescript-config.

## **Tech Stack Constraints**

* **Routing:** Expo Router v7 (File-based routing in /src/app).
* **State Management:** Zustand (Local UI state), TanStack React Query (Server/API state).
* **Storage:** react-native-mmkv (Synchronous). NO AsyncStorage.
* **Styling:** React Native StyleSheet (Default). NO NativeWind or Tailwind classes.
* **List Rendering:** @shopify/flash-list ONLY for arrays \> 20 items. NO FlatList.
* **Forms:** react-hook-form with zod validation schemas.

## **Environment & Testing**

* **Execution:** Assume Expo Development Builds (eas build \--profile development). Expo Go is unsupported due to native modules.
* **E2E Tests:** Written in declarative YAML using Maestro, located in the .maestro/ directory.
* **Push Notifications:** Handled via expo-notifications, requires explicit permission wrappers.

## **Boundary Violations (DO NOT DO THIS)**

* Do NOT output HTML/Web DOM elements (\<div\>, \<span\>, \<p\>). Use native primitives.
* Do NOT import legacy bridge-based native modules.
* Do NOT modify android/ or ios/ directories manually; use Expo Config Plugins.
* Do NOT use python:alpine base images in the FastAPI Dockerfile; use slim-bookworm.

## **7\. Minimal Practical Examples for the Fabrik Stack**

To effectively guide AI coding agents, providing minimal, syntactically correct examples of complex integration patterns is vastly superior to abstract descriptions. The following examples demonstrate the required patterns for connecting the FastAPI backend to the React Native frontend within the Fabrik constraints.

### **FastAPI WebSocket Connection Manager (Backend)**

This example demonstrates the robust connection management required for the ARM64 Coolify deployment, ensuring that dead sockets are properly reaped and memory leaks are avoided during cellular network disruptions.28

Python

\# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import logging

app \= FastAPI(title="Fabrik API")
logger \= logging.getLogger(\_\_name\_\_)

class ConnectionManager:
    def \_\_init\_\_(self):
        self.active\_connections: Dict \= {}

    async def connect(self, client\_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active\_connections\[client\_id\] \= websocket
        logger.info(f"Client {client\_id} connected.")

    def disconnect(self, client\_id: str):
        if client\_id in self.active\_connections:
            del self.active\_connections\[client\_id\]
            logger.info(f"Client {client\_id} disconnected.")

    async def send\_personal\_message(self, message: str, client\_id: str):
        if client\_id in self.active\_connections:
            await self.active\_connections\[client\_id\].send\_text(message)

manager \= ConnectionManager()

@app.websocket("/ws/{client\_id}")
async def websocket\_endpoint(websocket: WebSocket, client\_id: str):
    await manager.connect(client\_id, websocket)
    try:
        while True:
            data \= await websocket.receive\_text()
            \# Process incoming JSON payloads
            await manager.send\_personal\_message(f"Echo confirmed: {data}", client\_id)
    except WebSocketDisconnect:
        manager.disconnect(client\_id)

### **Zustand \+ MMKV Persistence Adapter (Frontend)**

This snippet illustrates how agents must configure local user interface state, utilizing the synchronous, memory-mapped storage capabilities of MMKV integrated directly into the Zustand middleware pipeline.12

TypeScript

// src/store/useSettingsStore.ts
import { create } from 'zustand';
import { persist, StateStorage, createJSONStorage } from 'zustand/middleware';
import { MMKV } from 'react-native-mmkv';

const storage \= new MMKV({ id: 'fabrik-global-storage' });

// Create an adapter matching Zustand's StateStorage interface
const zustandStorage: StateStorage \= {
  setItem: (name, value) \=\> {
    return storage.set(name, value);
  },
  getItem: (name) \=\> {
    const value \= storage.getString(name);
    return value?? null;
  },
  removeItem: (name) \=\> {
    return storage.delete(name);
  },
};

interface SettingsState {
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') \=\> void;
}

export const useSettingsStore \= create\<SettingsState\>()(
  persist(
    (set) \=\> ({
      theme: 'system',
      setTheme: (theme) \=\> set({ theme }),
    }),
    {
      name: 'settings-storage',
      storage: createJSONStorage(() \=\> zustandStorage),
    }
  )
);

### **React Hook Form \+ Zod Integration (Frontend)**

This snippet demonstrates the mandated approach to form validation, utilizing uncontrolled components to maintain high frame rates on mobile devices while ensuring type safety against the FastAPI schema requirements.

TypeScript

// src/components/LoginForm.tsx
import React from 'react';
import { View, TextInput, Button, Text, StyleSheet } from 'react-native';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const loginSchema \= z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type LoginFormData \= z.infer\<typeof loginSchema\>;

export const LoginForm \= () \=\> {
  const { control, handleSubmit, formState: { errors } } \= useForm\<LoginFormData\>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' }
  });

  const onSubmit \= (data: LoginFormData) \=\> {
    // Dispatch to React Query mutation here
    console.log(data);
  };

  return (
    \<View style\={styles.container}\>
      \<Controller
        control\={control}
        name\="email"
        render\={({ field: { onChange, onBlur, value } }) \=\> (
          \<TextInput
            style\={styles.input}
            onBlur\={onBlur}
            onChangeText\={onChange}
            value\={value}
            keyboardType\="email-address"
            autoCapitalize\="none"
          /\>
        )}
      /\>
      {errors.email && \<Text style\={styles.error}\>{errors.email.message}\</Text\>}

      \<Button title\="Submit" onPress\={handleSubmit(onSubmit)} /\>
    \</View\>
  );
};

const styles \= StyleSheet.create({
  container: { padding: 16 },
  input: { borderWidth: 1, borderColor: '\#ccc', padding: 10, marginBottom: 8 },
  error: { color: 'red', marginBottom: 16 },
});

## **8\. Recommended Final Content: MOBILE\_UI Rule Pack**

The following Markdown block contains the highly concentrated, agent-executable rule pack intended to be dropped directly into the Fabrik AI platform's configuration. It distills the extensive architectural reasoning into actionable directives.

# **FABRIK MOBILE\_UI AGENT RULE PACK**

**Target:** React Native \+ Expo SDK 55 (Managed Workflow)

**Role:** Expert Mobile Engineer

**Constraint:** Maximize durability; minimize operations. Solo developer context.

## **1\. MANDATORY ARCHITECTURE (Never Deviate)**

* **New Architecture Only:** Expo SDK 55 utilizes Fabric and JSI by default. Never generate code involving the legacy JSON bridge. Never set newArchEnabled=false.
* **UI Primitives Only:** You are in a React Native environment. Web DOM elements (\<div\>, \<span\>, \<p\>, \<img\>) are strictly forbidden. Use \<View\>, \<Text\>, and \<Image\>.
* **Strict TypeScript:** Enforce structural typing via @react-native/typescript-config. any types are prohibited. Interfaces must be explicitly exported.
* **Expo Managed Workflow:** Never suggest npx expo eject or manual modifications to android/ and ios/ directories. All native configuration belongs in app.json config plugins.

## **2\. STATE & DATA (Strict Segregation)**

* **Server State:** Use @tanstack/react-query for ALL asynchronous API requests to the FastAPI backend. Implement stale-time and cache management.
* **Local State:** Use zustand for global UI state. Do not use Redux or standalone React Context for high-frequency updates.
* **Persistence:** Use react-native-mmkv for fast, synchronous key-value storage. Never use AsyncStorage. Use expo-sqlite ONLY if complex relational queries are required.
* **Forms:** Use react-hook-form coupled with zod resolvers for validation. Do not use controlled state variables (useState) for text inputs.

## **3\. UI, STYLING & PERFORMANCE**

* **Styling:** Use React Native StyleSheet as the default. If complex adaptive theming is explicitly requested, use react-native-unistyles. **BANNED:** NativeWind/Tailwind (due to severe runtime overhead on mobile).
* **List Rendering:** **BANNED:** FlatList and \<ScrollView\>{array.map()}\</ScrollView\> for large datasets. **REQUIRED:** @shopify/flash-list.
* **Image Optimization:** Never use the standard \<Image\>. Always use expo-image for disk/memory caching and WebP support.
* **Safe Areas:** Never hardcode top/bottom padding. Always use useSafeAreaInsets from react-native-safe-area-context.

## **4\. NAVIGATION & DEEP LINKING**

* **Router:** Use expo-router (v7) exclusively. Utilize file-based routing within the /src/app directory.
* **Links:** Use the \<Link\> component from expo-router. For deep linking payloads, extract parameters via useGlobalSearchParams(). Rely on Universal Links, not custom URL schemes.

## **5\. HARDWARE & PERMISSIONS**

* **Push Notifications:** Use expo-notifications. Always wrap token generation (getExpoPushTokenAsync) in an explicit permission request block.
* **Platform Checks:** Use Platform.OS \=== 'ios' or Platform.select() for specific hardware variances. Never assume identical shadow or keyboard behavior across iOS and Android.

## **6\. BACKEND INTEGRATION (FastAPI)**

* **WebSockets:** Implement exponential backoff reconnection logic in the React Native useEffect. Ensure the cleanup function explicitly calls ws.close().
* **Docker Architecture:** FastAPI deployments on ARM64 must utilize python:3.12-slim-bookworm. **BANNED:** python:alpine (causes musl libc compilation failures).

## **7\. TESTING**

* **E2E Automation:** Write declarative End-to-End tests in YAML using Maestro. Save flows in the .maestro/ directory. Target elements using testID.
* **Unit/Component:** Use @testing-library/react-native and Jest.

## **8\. DEPLOYMENT & OTA**

* **Updates:** Configure Hermes bytecode diffing (enableBsdiffPatchSupport: true in app.json) for smaller OTA updates via EAS.
* **Builds:** Assume execution on EAS (eas build \--profile development). Code must never rely on the deprecated Expo Go environment.

#### **Works cited**

1. React Native's New Architecture \- Expo Documentation, accessed April 1, 2026, [https://docs.expo.dev/guides/new-architecture/](https://docs.expo.dev/guides/new-architecture/)
2. What's New in Expo SDK 55 \- Medium, accessed April 1, 2026, [https://medium.com/@onix\_react/whats-new-in-expo-sdk-55-6eac1553cee8](https://medium.com/@onix_react/whats-new-in-expo-sdk-55-6eac1553cee8)
3. React Native 0.82 \- A New Era, accessed April 1, 2026, [https://reactnative.dev/blog/2025/10/08/react-native-0.82](https://reactnative.dev/blog/2025/10/08/react-native-0.82)
4. \[v4\] Performance issues · nativewind nativewind · Discussion \#642 \- GitHub, accessed April 1, 2026, [https://github.com/nativewind/nativewind/discussions/642](https://github.com/nativewind/nativewind/discussions/642)
5. uni-stack/uniwind-benchmarks \- GitHub, accessed April 1, 2026, [https://github.com/uni-stack/uniwind-benchmarks](https://github.com/uni-stack/uniwind-benchmarks)
6. Introducing Uniwind \- The fastest Tailwind bindings for React Native : r/reactnative \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/reactnative/comments/1n84ib0/introducing\_uniwind\_the\_fastest\_tailwind\_bindings/](https://www.reddit.com/r/reactnative/comments/1n84ib0/introducing_uniwind_the_fastest_tailwind_bindings/)
7. Why is Unistyles Goated | Ali Alshehri, accessed April 1, 2026, [https://www.ali-sh.com/posts/why-is-unistyles-goated](https://www.ali-sh.com/posts/why-is-unistyles-goated)
8. Do You Need State Management in 2025? React Context vs Zustand vs Jotai vs Redux, accessed April 1, 2026, [https://dev.to/themachinepulse/do-you-need-state-management-in-2025-react-context-vs-zustand-vs-jotai-vs-redux-1ho](https://dev.to/themachinepulse/do-you-need-state-management-in-2025-react-context-vs-zustand-vs-jotai-vs-redux-1ho)
9. Zustand vs Jotai vs Recoil for State Management in React Apps 2026 \- Index.dev, accessed April 1, 2026, [https://www.index.dev/skill-vs-skill/zustand-vs-jotai-vs-recoil](https://www.index.dev/skill-vs-skill/zustand-vs-jotai-vs-recoil)
10. Why choose Zustand over Jotai? : r/reactjs \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/reactjs/comments/1ctsnov/why\_choose\_zustand\_over\_jotai/](https://www.reddit.com/r/reactjs/comments/1ctsnov/why_choose_zustand_over_jotai/)
11. How to Persist State with AsyncStorage and MMKV in React Native \- OneUptime, accessed April 1, 2026, [https://oneuptime.com/blog/post/2026-01-15-react-native-asyncstorage-mmkv/view](https://oneuptime.com/blog/post/2026-01-15-react-native-asyncstorage-mmkv/view)
12. Choosing the Right Storage Solution \- DEV Community, accessed April 1, 2026, [https://dev.to/cathylai/choosing-the-right-storage-solution-3log](https://dev.to/cathylai/choosing-the-right-storage-solution-3log)
13. When to use AsyncStorage vs React Native SQLite? : r/reactnative \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/reactnative/comments/1djd7ws/when\_to\_use\_asyncstorage\_vs\_react\_native\_sqlite/](https://www.reddit.com/r/reactnative/comments/1djd7ws/when_to_use_asyncstorage_vs_react_native_sqlite/)
14. React Navigation 7: The Performance Updates Nobody's Talking About | by noman akram, accessed April 1, 2026, [https://medium.com/@nomanakram1999/react-navigation-7-the-performance-updates-nobodys-talking-about-c9e36d7cbd4a](https://medium.com/@nomanakram1999/react-navigation-7-the-performance-updates-nobodys-talking-about-c9e36d7cbd4a)
15. What's new in Expo SDK 55 \- YouTube, accessed April 1, 2026, [https://www.youtube.com/watch?v=q72aeXsbF9c](https://www.youtube.com/watch?v=q72aeXsbF9c)
16. React Native Deep Linking: Expo Router Full Implementation \- Zignuts Technolab, accessed April 1, 2026, [https://www.zignuts.com/blog/deep-linking-react-native-expo-router](https://www.zignuts.com/blog/deep-linking-react-native-expo-router)
17. Deep Linking in React Native (Expo): A Complete Guide (From Someone Who Just Spent Hours Debugging This) | by Shreyasdamase | Medium, accessed April 1, 2026, [https://medium.com/@shreyasdamase/deep-linking-in-react-native-expo-a-complete-guide-from-someone-who-just-spent-hours-debugging-38baeed51850](https://medium.com/@shreyasdamase/deep-linking-in-react-native-expo-a-complete-guide-from-someone-who-just-spent-hours-debugging-38baeed51850)
18. ScrollView vs FlatList vs FlashList in React Native: Understanding List Performance, accessed April 1, 2026, [https://medium.com/@csta.puja/scrollview-vs-flatlist-vs-flashlist-in-react-native-understanding-list-performance-e6b34334a079](https://medium.com/@csta.puja/scrollview-vs-flatlist-vs-flashlist-in-react-native-understanding-list-performance-e6b34334a079)
19. FlashList v2: A ground-up rewrite for React Native's New Architecture \- Shopify Engineering, accessed April 1, 2026, [https://shopify.engineering/flashlist-v2](https://shopify.engineering/flashlist-v2)
20. Expo SDK 55 \- Expo Changelog, accessed April 1, 2026, [https://expo.dev/changelog/sdk-55](https://expo.dev/changelog/sdk-55)
21. Permissions \- Expo Documentation, accessed April 1, 2026, [https://docs.expo.dev/guides/permissions/](https://docs.expo.dev/guides/permissions/)
22. Expo Go Push Notifications: Complete Implementation Guide (SDK 52+) \- Courier, accessed April 1, 2026, [https://www.courier.com/blog/expo-notifications](https://www.courier.com/blog/expo-notifications)
23. Ship smaller OTA updates: bundle diffing comes to EAS Update in SDK 55 \- Expo, accessed April 1, 2026, [https://expo.dev/blog/ship-smaller-ota-updates-bundle-diffing-comes-to-ota-updates-in-sdk-55](https://expo.dev/blog/ship-smaller-ota-updates-bundle-diffing-comes-to-ota-updates-in-sdk-55)
24. Optimizing Dockerized FastAPI with TensorFlow: How to reduce a 1.57GB Image Size?, accessed April 1, 2026, [https://www.reddit.com/r/FastAPI/comments/1e1lal6/optimizing\_dockerized\_fastapi\_with\_tensorflow\_how/](https://www.reddit.com/r/FastAPI/comments/1e1lal6/optimizing_dockerized_fastapi_with_tensorflow_how/)
25. Containerizing a Python FastAPI Application with Docker (and Solving ARM vs x86 Architecture Issues) \- DEV Community, accessed April 1, 2026, [https://dev.to/jayakrishnayadav24/containerizing-a-python-fastapi-application-with-docker-and-solving-arm-vs-x86-architecture-1gfh](https://dev.to/jayakrishnayadav24/containerizing-a-python-fastapi-application-with-docker-and-solving-arm-vs-x86-architecture-1gfh)
26. How to Containerize a FastAPI Application with Docker \- OneUptime, accessed April 1, 2026, [https://oneuptime.com/blog/post/2026-02-08-how-to-containerize-a-fastapi-application-with-docker/view](https://oneuptime.com/blog/post/2026-02-08-how-to-containerize-a-fastapi-application-with-docker/view)
27. Server-Sent Events vs WebSockets: Key Differences and Use Cases in 2026 \- Nimble Way, accessed April 1, 2026, [https://www.nimbleway.com/blog/server-sent-events-vs-websockets-what-is-the-difference-2026-guide](https://www.nimbleway.com/blog/server-sent-events-vs-websockets-what-is-the-difference-2026-guide)
28. How to Implement WebSocket Connections in Python with FastAPI \- OneUptime, accessed April 1, 2026, [https://oneuptime.com/blog/post/2025-01-06-python-websocket-fastapi/view](https://oneuptime.com/blog/post/2025-01-06-python-websocket-fastapi/view)
29. How to Set Up End-to-End Testing for React Native with Maestro \- OneUptime, accessed April 1, 2026, [https://oneuptime.com/blog/post/2026-01-15-react-native-maestro-testing/view](https://oneuptime.com/blog/post/2026-01-15-react-native-maestro-testing/view)
30. React Native Automation: Setup Guide \- Maestro, accessed April 1, 2026, [https://maestro.dev/insights/react-native-automation-setup-guide](https://maestro.dev/insights/react-native-automation-setup-guide)
31. Native E2E Testing With Expo and Maestro in 5 steps \- Medium, accessed April 1, 2026, [https://medium.com/lingvano/native-e2e-testing-with-maestro-and-expo-14e9e9b0f0fe](https://medium.com/lingvano/native-e2e-testing-with-maestro-and-expo-14e9e9b0f0fe)
32. Expo now supports Maestro Cloud testing in your CI workflow, accessed April 1, 2026, [https://expo.dev/blog/expo-now-supports-maestro-cloud-testing-in-your-ci-workflow](https://expo.dev/blog/expo-now-supports-maestro-cloud-testing-in-your-ci-workflow)
33. Strict TypeScript API (opt in) \- React Native, accessed April 1, 2026, [https://reactnative.dev/docs/strict-typescript-api](https://reactnative.dev/docs/strict-typescript-api)
34. Mastering TypeScript Best Practices to Follow in 2026 \- Bacancy Technology, accessed April 1, 2026, [https://www.bacancytechnology.com/blog/typescript-best-practices](https://www.bacancytechnology.com/blog/typescript-best-practices)
35. Expo SDK 55 Beta is now available, accessed April 1, 2026, [https://expo.dev/changelog/sdk-55-beta](https://expo.dev/changelog/sdk-55-beta)
36. Building shared coding guidelines for AI (and people too) \- Stack Overflow, accessed April 1, 2026, [https://stackoverflow.blog/2026/03/26/coding-guidelines-for-ai-agents-and-people-too/](https://stackoverflow.blog/2026/03/26/coding-guidelines-for-ai-agents-and-people-too/)
37. Run E2E tests on EAS Workflows and Maestro \- Expo Documentation, accessed April 1, 2026, [https://docs.expo.dev/eas/workflows/examples/e2e-tests/](https://docs.expo.dev/eas/workflows/examples/e2e-tests/)
38. Configuring Expo Build Properties for Your Project | by Devin Rosario, accessed April 1, 2026, [https://javascript.plainenglish.io/expo-build-properties-configuration-complete-guide-2025-38cd1ebf946c](https://javascript.plainenglish.io/expo-build-properties-configuration-complete-guide-2025-38cd1ebf946c)
39. Struggling with Expo Go Incompatibility & EAS Build Costs – Need Advice \- Reddit, accessed April 1, 2026, [https://www.reddit.com/r/expo/comments/1l80wvh/struggling\_with\_expo\_go\_incompatibility\_eas\_build/](https://www.reddit.com/r/expo/comments/1l80wvh/struggling_with_expo_go_incompatibility_eas_build/)
40. Using TypeScript \- React Native, accessed April 1, 2026, [https://reactnative.dev/docs/typescript](https://reactnative.dev/docs/typescript)
41. no-extend-native \- ESLint \- Pluggable JavaScript Linter, accessed April 1, 2026, [https://eslint.org/docs/latest/rules/no-extend-native](https://eslint.org/docs/latest/rules/no-extend-native)
42. AGENTS.md — a simple, open format for guiding coding agents · GitHub, accessed April 1, 2026, [https://github.com/agentsmd/agents.md](https://github.com/agentsmd/agents.md)
43. Improve your AI code output with AGENTS.md (+ my best tips) \- Builder.io, accessed April 1, 2026, [https://www.builder.io/blog/agents-md](https://www.builder.io/blog/agents-md)
