#!/bin/bash

if ! command -v jq &> /dev/null; then
    echo "jq is required but not installed. Please install jq."
    exit 1
fi

if [ ! -f config.json ]; then
    echo "config.json file not found!"
    exit 1
fi

for bot in $(jq -r 'to_entries[] | "\(.key),\(.value.source),\(.value.branch // "main")"' config.json); do
  name=$(echo $bot | cut -d',' -f1)
  source=$(echo $bot | cut -d',' -f2)
  branch=$(echo $bot | cut -d',' -f3)

  if [ -d "$name" ]; then
    echo "Directory $name already exists, pulling latest changes..."
    cd $name
    git fetch origin
    git checkout $branch
    git pull origin $branch
  else
    echo "Cloning repository $source on branch $branch into $name..."
    git clone --branch $branch $source $name || { echo "Failed to clone $name"; continue; }
    cd $name
  fi
  
  if [ -f "requirements.txt" ]; then
    echo "Installing/updating dependencies for $name..."
    pip install --no-cache-dir -r requirements.txt || { echo "Failed to install dependencies for $name"; cd ..; continue; }
  else
    echo "No requirements.txt found for $name, skipping dependency installation."
  fi

  cd ..
done
