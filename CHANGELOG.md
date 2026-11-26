# Changelog

**English** · [Polski](CHANGELOG.pl.md)

## 0.1.5 — development candidate (unreleased)

- Fix entity names being replaced by the device name: translated entities no longer set `_attr_name`, including to `None`.
- Regression test exercises all translated entity constructors in both languages and checks stable unique IDs.
- No changes to device commands, event provisioning or existing webhook identifiers.

## 0.1.4 — development candidate (unreleased)

- Native Home Assistant Polish and English entity names, input event labels and translated errors.
- Readable Python modules and reproducible standalone installer build.
- Preserve native translation resources and existing entity unique IDs and event identifiers.
- Additional translation and build regression tests. Hardware validation of this candidate is pending.

## 0.1.3 — beta (2026-11-26)

- Native HA event entities for IN1 and IN2.
- Local secret webhooks and explicit action provisioning with read-back checks.
- IN2 event classification based on the current handle setting.
- Seven IN2 events verified on W-dU-2.0 firmware 0.1060 with HA Core 2026.11.3.
- Dedicated HA electric-strike release confirmed on the physical installation by its owner.
- API observations, offline regression tests and CI installer artifact.

## 0.1.2

- Initial WIKĘD overlay: three LED outputs, timed lighting, handle setting, S1/S2, optional release button and native update/cover support.
