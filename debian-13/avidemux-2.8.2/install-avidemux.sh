#!/bin/bash
  
  sudo apt install -y --no-install-recommends libfaac0t64  libqt6network6  libqt6opengl6  libqt6openglwidgets6
  sudo dpkg -i *.deb
  sudo apt install -f -y --no-install-recommends


  sudo sed -i "s/Exec=avidemux3_qt6 %f/Exec=env QT_SCALE_FACTOR=1.5 avidemux3_qt6 %f/g" /usr/share/applications/org.avidemux.Avidemux.desktop



  #sed -i "s/Exec=avidemux3_qt6 %f/Exec=env QT_SCALE_FACTOR=1.5 avidemux3_qt6 %f/g" ~/Desktop/org.avidemux.Avidemux.desktop
