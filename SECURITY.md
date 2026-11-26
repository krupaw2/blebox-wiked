# Security

This project controls physical access hardware. Report suspected security issues privately to the repository maintainer; do not post webhook identifiers, access tokens, private URLs, packet captures or detailed home configurations in public issues. If GitHub private vulnerability reporting is enabled, use it.

## Safety boundaries

- Native conditional release is retained; incoming events do not release the door.
- Webhook identifiers are secret, persistent and local-only; keep HA and the controller on a trusted network. Local HTTP is not encrypted.
- Never expose the controller API directly to the internet.
- Configuration writes are explicit and use separate action slots. Back up the device configuration before provisioning.
- Use S1/S2 as lock signals, not proof of door closure.
- This beta is tested on the versions in README; other versions and wiring configurations may behave differently.
