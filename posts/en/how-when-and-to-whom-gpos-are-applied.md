---
id: "como-cuando-y-a-quien-se-aplican-las-gpo"
title: "How, When, and to Whom GPOs Are Applied"
author: "juan-antonio-gonzalez-mena"
publishedDate: 2026-02-14
updatedDate: 2026-02-14
image: "https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-0.webp"
description: "Discover how Group Policy Objects (GPO) work in Active Directory: LSDOU processing order, inheritance, security filtering, preferences, and execution context."
categories:
  - "active-directory"
draft: false
featured: false
lang: "en"
---

In the previous article, we took a brief look at Group Policies. We discussed their components and attributes. If you haven't read that article, you can check it out at the following link:

- [Introduction to Group Policy Objects (GPO) in Active Directory](https://blog.deephacking.tech/en/posts/introduction-to-group-policy-objects-gpo-active-directory/)

Today we're going to dive a bit deeper and answer some important questions, such as:

- How, when, to whom, and in what order are GPOs applied?
- What happens if a container has more than one GPO applied?
- If these GPOs overlap in their configurations, what happens?
- If an inherited GPO from a parent container sets a configuration and another directly applied GPO indicates the opposite, which one prevails?
- Is there a way to filter who a GPO is applied to? That is, so it doesn't affect the entire container, but only certain computers or users.
- In what context do the processes that apply GPOs run?

Let's get into it, grab a coffee for what's coming.

- [Group Policy Application Flow](#group-policy-application-flow)
  - [Group Policy Inheritance](#group-policy-inheritance)
    - [Multiple GPOs in the Same Container](#multiple-gpos-in-the-same-container)
    - [Blocking or Enforcing Inheritance](#blocking-or-enforcing-inheritance)
  - [Group Policy Filtering](#group-policy-filtering)
    - [Security Filtering](#security-filtering)
    - [WMI Filtering](#wmi-filtering)
    - [GPO Application Order](#gpo-application-order)
  - [Group Policy Preferences (GPP)](#group-policy-preferences-gpp)
  - [When and How GPOs Are Processed](#when-and-how-gpos-are-processed)
    - [Foreground - Initial Processing](#foreground---initial-processing)
    - [Background - Periodic Refresh](#background---periodic-refresh)
    - [Execution Context (Client-Side)](#execution-context-client-side)
- [Conclusion](#conclusion)
- [References](#references)

## Group Policy Application Flow

Let's start by discussing the flow that occurs when a GPO is applied. When you configure a GPO, it's as simple as setting the configuration you want, specifying who you want to apply it to, and forgetting about it; the rest of the process happens automatically. When a computer or user affected by the GPO we just created connects to the network, it will automatically receive this new configuration and apply it.

We don't need to understand much about that process right now, but what is truly important is understanding the processing levels and precedence of GPOs.

There are 4 hierarchy levels in Group Policies:
- Local
- Site
- Domain
- OU

These hierarchy levels define where a GPO can be applied. As you can see, in Active Directory you can apply a GPO to sites, domains, or organizational units, and then, separately, there's each Windows local group policy.

At the same time these are the 4 hierarchy levels, they're also the processing order, commonly called `LSDOU`. The first policy to be processed is the local policy, and the last is the organizational unit policy. The fact that the local policy is processed first doesn't mean it has higher priority. In fact, it's the opposite: in case of conflict, the last processed policy prevails. In the `LSDOU` order, the policy applied to the organizational unit has higher priority because it's closest to the object.

Understanding this is especially important when there are conflicts between policies; imagine a local policy tells an object the opposite of what the organizational unit policy tells it, which one should it obey? It will follow the policy considered closest, the organizational unit policy.

The following diagram allows you to visualize much more easily what I just explained:

![LSDOU GPO processing order diagram](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-1.avif)

This precedence order is the most common because it's the default, although it's possible to modify the order. In any case, from these existing hierarchy levels, we can draw some conclusions that help us better understand all of this:
- Since the local policy is processed first, any configuration within an Active Directory policy has the potential to modify or override that local configuration.
- Site-level policies that a computer receives will change depending on the physical location it's connected to, so this configuration can be variable. In Active Directory, sites are defined using IP address ranges or subnets, which allows computers to be associated with a specific site based on where they connect.
- Any domain-level policy configuration will prevail over any site policy, in case of conflicts.
- The policy linked to the organizational unit will always prevail (under normal conditions).

Now, what happens if there are multiple Group Policies linked to the same organizational unit, domain, or site and there are conflicts between them? What can also happen if there are organizational units within other organizational units and they cause conflicts among themselves? In these cases, what prevails?

To understand these more complex cases, we need to talk about inheritance.

### Group Policy Inheritance

By default, Group Policies are inherited. This means that a GPO linked to a parent container (site, domain, or OU) is automatically applied to all objects (users and computers) in child containers. This allows a definition at a high level in the chain to reach all the way down without repeating effort. Additionally, we already know the processing order and precedence, which follows the `LSDOU` model.

In cases where there are nested organizational units, the model would recursively expand to the following:
- Local
- Site
- Domain
- OU (parent)
- Child OU
- Grandchild OU (and so on)

In case of conflict between configurations at different levels, the one closest to the object (user or computer) always prevails. For example:
- A GPO linked to the domain blocks USB devices.
- Another GPO linked to the "IT" OU allows them.

IT computers will be able to use USB because the OU GPO is processed later and overwrites the domain GPO.

#### Multiple GPOs in the Same Container

When there are multiple GPOs linked to the same OU, site, or domain, they appear in an ordered list that can be viewed in the _Group Policy Management (GPMC)_:

<figure>

![Linked Group Policy Objects tab of the Crownlands OU](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-2.avif)

<figcaption>

Linked Group Policy Objects tab of the Crownlands OU

</figcaption>

</figure>

GPOs are processed from bottom to top, meaning the GPO with the lowest _link order_ (usually the one at the top, with number 1) is the last to be applied and, therefore, wins in case of conflict.

You can manually change the order with the ↑ ↓ arrows. This is precisely what allows you to modify the default precedence within the same level.

#### Blocking or Enforcing Inheritance

Sometimes the default inheritance doesn't fit the organization's requirements. For example:
- An OU needs very specific configurations and shouldn't be affected by unnecessary inherited policies.
- Applying many inherited GPOs increases processing time.
- If requirements are covered by directly linked GPOs, it's more efficient to avoid inherited ones.

In these cases, there are two key mechanisms: **Block Inheritance** and **Enforced**. Both are controlled through specific attributes on Active Directory container objects.

##### 1. Block Inheritance

It's activated at the container level (OU or domain, although it's uncommon on the root domain). When enabled, that container and its descendants ignore all GPOs inherited from higher levels; only directly linked GPOs and those marked as **Enforced** are applied.

This feature is controlled through the `gpOptions` attribute. Its two possible values are as follows:

| Value | Meaning |
|-------|---------|
| `0`   | Inheritance enabled (default value). |
| `1`   | Inheritance blocked (*Block Inheritance*): GPOs from parent containers are not applied, except those marked as enforced. |

##### 2. Enforced (No Override)

It's activated at the **link** level, not on the GPO itself. This means the same GPO can be enforced in one container and not enforced in another. A link marked as **Enforced**:
- Is always applied, even if the target container has **Block Inheritance** enabled.
- Has higher precedence than any non-enforced GPO, regardless of its position in the hierarchy.

The attribute used to control this mechanism is `gpLink`. We mentioned this attribute in the previous article; I'll use the same example:

```plaintext
[LDAP://CN={A1B2C3D4-1111-2222-3333-ABCDEF123456},CN=Policies,CN=System,DC=sevenkingdoms,DC=local;0]
[LDAP://CN={B2C3D4E5-4444-5555-6666-123456ABCDEF},CN=Policies,CN=System,DC=sevenkingdoms,DC=local;2]
```

This attribute is present on domains, sites, and organizational units. It defines the GPOs linked to the container and how they are applied. If we take one line from the example above and separate it by semicolon, we get two parts:
- **The linked GPO**, identified by its DN:
  - `LDAP://CN={A1B2C3D4-...},CN=Policies,CN=System,DC=sevenkingdoms,DC=local`
- **The link state**, represented by a numeric value:
  - `0`

Additionally, the position of each entry within the attribute determines its **precedence order**. Entries are processed sequentially: the first is applied first and the last is applied last. In case of conflict, the last entry overwrites the previous ones, so it has **higher priority**.

The link state is what determines whether a GPO is enforced in a container or not. Its possible values are:

| Value | Meaning |
|-------|---------|
| `0`   | Link enabled. |
| `1`   | Link disabled. |
| `2`   | Link enabled and enforced (*Enforced*). |
| `3`   | Link disabled and enforced. |


---

The following diagram shows an example of the behavior of both concepts:

<figure>

![Block Inheritance and Enforced diagram in GPO](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-3.avif)

<figcaption>

Inspired by the diagram from the article _[A Red Teamer's Guide to GPOs and OUs](https://wald0.com/?p=179)_ by wald0

</figcaption>

</figure>

The `Custom Password Policy` GPO is linked to the domain object. In this case, this GPO is enforced, so it will apply to all child objects regardless of the `Sysadmins` OU having inheritance blocked. Likewise, only those GPOs inherited from above that are enforced will apply to the `Sysadmins` OU, as well as the GPOs that are directly linked to its organizational unit.

In summary, blocking inheritance isolates you, but if a GPO is enforced, isolation doesn't matter: it always reaches you. This combination is what allows precise control over which policies reach (or don't reach) each corner of the domain.

- What happens if there are multiple enforced GPOs with conflicting configurations?

All enforced GPOs are processed at the very end, after normal GPOs. Within enforced GPOs, the order is as follows:
- Between different levels: It works in reverse compared to normal GPOs, they are applied from bottom to top in the hierarchy (first child OU, then parent OU, domain, and site). That's why the enforced GPO at the highest level (domain or site) always prevails.
- Within the same level: Same as with normal GPOs, the one with the lowest link order (the one at the top of the list) wins.

### Group Policy Filtering

So far, we've seen how inheritance, link order, **Block Inheritance**, and **Enforced** decide which GPOs reach an entire container (site, domain, or OU).

But what happens if within the same OU you have users or computers that need different rules? Moving them to another OU is an option, but sometimes it's not practical or it breaks the logical structure of the domain.

This is where filters come in. Let's look at the two existing ways to fine-tune who actually receives a GPO, even within the same container.

#### Security Filtering

By default, any GPO linked to a site, domain, or OU is applied to all authenticated objects in that container thanks to the special `Authenticated Users` group, which has `Read` and `Apply Group Policy` permissions.

![Default security filtering with Authenticated Users](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-4.avif)

To restrict the GPO to certain objects:
1. Remove `Authenticated Users` from security filtering.
2. Add the objects (users, computers, or groups) to which you do want to apply the GPO.
3. In the `Delegation` tab, ensure that `Authenticated Users` (or `Domain Computers`) retains the `Read` permission, but does **not** have `Apply Group Policy`.

Step 3 is necessary due to the `MS16-072` patch: since then, GPOs are read in the context of the computer account, so the computer must be able to read the GPO even if it's not directly applied to it.

![Delegation tab with Apply Group Policy permissions](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-5.avif)

> If you only want to exclude certain objects, you can leave the default filtering (`Authenticated Users`) and in the `Delegation` tab add the group or object to exclude and deny them the `Apply Group Policy` permission.

#### WMI Filtering

This filter is **evaluated on the computer** through WMI (*Windows Management Instrumentation*) queries. If the condition is not met, **the entire GPO is discarded** (both computer and user configuration). This allows filtering by operating system version, architecture, registry values, etc. An example:

```sql
SELECT * FROM Win32_OperatingSystem WHERE Version LIKE "10.%" AND OSArchitecture = "64-bit"
```

As a note, the same WMI filter can be associated with many GPOs, but a GPO can only have one WMI filter.

#### GPO Application Order

After everything we've covered, when a computer or user processes a GPO, the filters are evaluated in this order:
1. **LSDOU + inheritance + Link Order + Block/Enforced**: determines which GPOs reach the container.
2. **Security Filtering**: if the object doesn't have `Read` and `Apply Group Policy` permissions → the GPO is discarded.
3. **WMI Filtering**: if the WMI query is not satisfied on the computer, the GPO is discarded.

In short:
- **Security filtering** controls **who** it's applied to: specific users, computers, or groups.
- **WMI filtering** controls **under what conditions** it's applied: operating system version, architecture, etc.

### Group Policy Preferences (GPP)

So far, we've seen two levels of control:
1. **Policies** decide **what configuration** is applied (and enforce it: the user cannot change it while it's active).
2. **Filters** (security and WMI) decide **to whom** and **under what conditions** that configuration is applied.

But there's a practical problem: imagine you need to map a network drive for all users in an OU, except for those in the finance department, who need a different drive. With the tools you already know, your options are:
- Create another OU just for finance (breaks the structure if it doesn't make organizational sense).
- Create another GPO with security filtering (it works, but you multiply GPOs for each specific case).

**Group Policy Preferences** (*GPP*) solve this type of situation. They are configured within the same GPO, in the `Preferences` sections of `Computer Configuration` and `User Configuration`:

![GPO preferences menu](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-6.avif)

The fundamental difference from classic policies is twofold:

| | Classic Policies | Preferences (GPP) |
|---|---|---|
| **Behavior** | Enforce a value; the user cannot change it while the policy is applied. | Set an initial value; the user can modify it afterwards (although it reapplies on the next refresh). |
| **Filtering granularity** | Filtered at the **entire GPO** level (Security Filtering, WMI). | Each individual preference has its own filtering through **Item-Level Targeting**. |

**Item-Level Targeting** allows each element within the same GPO (a mapped drive, a printer, a shortcut...) to have its own application conditions, combinable with AND/OR: security group, IP subnet, OS version, computer name, etc.

Going back to the previous example: instead of creating another OU or multiplying GPOs, you can have a single GPO with two drive mapping preferences, each with its own _Item-Level Targeting_ pointing to a different security group. All within the same container and the same GPO.

In many environments, GPP is used for everyday tasks (drive mapping, printers, shortcuts, environment variables, registry keys, etc.) that classic policies don't handle well or that would require an unnecessarily complex structure of OUs and GPOs.

> **Note:** GPP may sound familiar to you because passwords used to be stored in them (the `cPassword` attribute). They were encrypted with AES, until Microsoft accidentally published the key. The vulnerability was patched with **MS14-025**, but it's still possible to find `cPasswords` in legacy environments.

### When and How GPOs Are Processed

At this point, we know very well which GPOs are applied and in what order; it's also important to understand when, how, and in what context they are processed.

GPOs are divided into two main categories:
- **Computer Configuration**: processed at computer startup.
- **User Configuration**: processed at user logon.

![Computer and user configuration in GPO](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-7.avif)

Each GPO can contain different types of configuration (registry, security, scripts, folder redirection, etc.). On the client side, each type is managed by a **Client-Side Extension (CSE)**: a specialized DLL that knows how to apply that specific type of configuration. The core engine that orchestrates the entire process is called **GP Core**, and it's the one that decides which CSE to invoke at each moment. We'll see both components in more detail at the end of this section.

There are two main processing modes:

#### Foreground - Initial Processing

Occurs at the following moments:
- When the computer is turned on (computer configuration).
- When the user logs on (user configuration).

Within foreground processing, there are two sub-modes:
- **Synchronous:** The system waits for all GPOs to finish applying before showing the desktop. It's slower, but everything is applied from the first moment. This was the default mode in **Windows 2000**.
- **Asynchronous:** Default mode since **Windows XP / Server 2003**. The system doesn't wait: the desktop appears quickly while GPOs are applied in parallel. This speeds up logons, but it implies that some configurations may need **two foreground processing cycles** (a restart + a logon) to apply completely. This behavior is known as **Fast Logon Optimization**.

Certain CSEs, such as **software installation** and **folder redirection**, require synchronous processing. When they detect pending changes, they temporarily disable _Fast Logon Optimization_ to ensure they are applied before the user accesses the desktop.

#### Background - Periodic Refresh

Once the computer has started and the user has logged on, GPOs are reprocessed periodically:
- **Clients:** every **90 minutes**, with a **random offset of up to 30 minutes** to avoid saturating the domain controller (refreshes are distributed between 90 and 120 minutes).
- **Domain controllers:** every **5 minutes**, with no random offset.

During the refresh, the client compares the **version number** of each GPO (stored in the GPC in the directory and in the GPT in SYSVOL). If it detects a change, it reprocesses the affected CSEs. If there are no changes, most CSEs skip reprocessing.

This has an important implication from an offensive standpoint: if someone locally modifies a configuration controlled by a GPO, but the GPO hasn't been modified in the directory, the next refresh won't detect changes and **won't revert the local modification**.

This makes GPOs vulnerable when users have local administrator privileges: a local administrator can undo almost any GPO configuration persistently, until something forces a complete reapplication.

To force reapplication, simply make any change to the GPO (even a trivial one), which increments its version number and causes all computers to reprocess it in the next cycle.

- **Exception: Security Client-Side Extension**

Not all CSEs depend on version changes. The **Security CSE** reapplies all security configurations every **16 hours** by default (controlled by `MaxNoGPOListChangesInterval`), regardless of whether the GPO has changed or not.

This is an intentional security measure: it ensures that critical settings such as password policies, firewall configuration, auditing, or user rights are automatically restored if someone with local access has tampered with them. This way, even if an attacker temporarily modifies a security configuration, at most 16 hours later the GPO will enforce it again.

This interval is enabled by default, but can be modified or disabled.

#### Execution Context (Client-Side)

All GPO processing is strictly a client-side operation: the computer queries the domain controller, determines the applicable policies, and applies them locally.

Two main components are involved in this process:
- **GP Core:** The core engine that compares GPO versions and examines the `gPCMachineExtensionNames` / `gPCUserExtensionNames` attributes of the GPC object to determine which CSEs should be invoked.
- **Client-Side Extensions (CSE):** DLLs registered on the client (identified by GUID) that perform the work of applying specific configurations (registry policies, security, scripts, folder redirection, software installation, etc.).

All processing (both GP Core and CSEs) runs with maximum privileges, in the context of the **Local System** account. However, when user configurations (*Per-User*) are applied, CSEs that need access to user profile resources (such as `HKEY_CURRENT_USER` or redirected folders) perform a temporary *impersonation* of the logged-on user's token.

This allows privileged configurations to be made without needing to grant local administrator privileges to the user.

## Conclusion

In this article, we've covered the entire lifecycle of a GPO from when it's linked to a container until it's applied on the user's computer. We've seen how the **LSDOU** model establishes the base processing order, how **inheritance** propagates policies throughout the hierarchy, and how the **Block Inheritance** and **Enforced** mechanisms allow breaking or imposing that inheritance when the situation requires it.

We've also explored the filtering tools (**Security Filtering** and **WMI Filtering**) that allow fine-tuning who and under what conditions each GPO is applied, and how **Group Policy Preferences (GPP)** fill the gap that classic policies leave in everyday tasks, offering a level of granularity that avoids unnecessarily multiplying OUs and GPOs.

Finally, we've gotten into the actual processing: **foreground** and **background** modes, the difference between synchronous and asynchronous processing, the change detection mechanism based on versions, and the **Local System** execution context with token impersonation for user configurations.

With all this, you now have a solid foundation to understand not only how GPOs work, but also where their weak points are: from the persistence of local changes when there's no modification in the GPO, to the implications of a user having local administrator privileges. In the next article, we'll continue pulling on the thread.

## References
- [Group Policy processing - Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing)
- [A Red Teamer's Guide to GPOs and OUs - wald0](https://wald0.com/?p=179)
- [Group policies in cyberattacks - Securelist](https://securelist.com/group-policies-in-cyberattacks/115331/)
- [Understanding Group Policy Storage - SDM Software](https://sdmsoftware.com/whitepapers/understanding-group-policy-storage/)
- [Sneaky Active Directory Persistence Tricks - ADSecurity](https://adsecurity.org/?p=2716)
- Mastering Windows Group Policy - Jordan Krause
- Mastering Active Directory - Dishan Francis
