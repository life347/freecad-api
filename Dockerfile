FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev python3-venv \
    wget git build-essential cmake \
    assimp-utils \
    xvfb \
    libglu1-mesa libxi6 libxrender1 libxext6 \
    freecad \
    && rm -rf /var/lib/apt/lists/*

# Create symlink for FreeCADCmd (Ubuntu package installs it as freecad)
RUN ln -s /usr/bin/freecad /usr/bin/FreeCADCmd

WORKDIR /app

COPY ./app /app
COPY requirements.txt /app/requirements.txt

RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Set up virtual display for FreeCAD
ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=offscreen

EXPOSE 8000

# Start Xvfb and then the application
CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x24 -ac +extension GLX +render -noreset & uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"]
