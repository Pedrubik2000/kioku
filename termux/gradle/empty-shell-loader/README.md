Project directory for `:shell-loader` (see settings.gradle). termux-x11's
`:shell-loader:stub` needs a `:shell-loader` parent project, but this app does
not build termux-x11's own shell loader, so the parent is empty. This file
exists because git does not keep empty directories.
