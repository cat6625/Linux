#!/bin/bash

  sudo apt install -y qt6-base-dev
  sudo dpkg -i *.deb
  sudo apt install -f -y --no-install-recommends



  cat << EOF | sudo tee /usr/share/applications/avidemux2.8.2-qt.desktop
#!/usr/bin/env xdg-open
[Desktop Entry]
Name=Avidemux 2.8.2 (Qt)
GenericName=Qt Video Editor
Comment=Edit your Videos
Comment[de]=Videos bearbeiten
TryExec=avidemux3_qt6
Exec=avidemux3_qt6
Icon=avidemux-48.png
Terminal=false
Type=Application
Categories=Qt;AudioVideo
MimeType=video/mpeg;video/x-mpeg;video/x-avi;application/x-flash-video;application/x-shockwave-flash;video/flv
EOF


  cat << EOF | sudo tee /usr/share/applications/avidemux2.8.2-jobs.desktop
#!/usr/bin/env xdg-open
[Desktop Entry]
Name=Avidemux 2.8.2 (Jobs)
GenericName=Video Editor Jobs application
TryExec=avidemux3_jobs_qt6
Exec=avidemux3_jobs_qt6
Icon=avidemux-48.png
Terminal=false
Type=Application
Categories=AudioVideo
EOF



