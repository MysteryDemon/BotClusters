for bot in $(cat config.json | jq -r 'to_entries[] | "\(.key),\(.value.source),\(.value.branch)"'); do
  name=$(echo $bot | cut -d',' -f1);
  source=$(echo $bot | cut -d',' -f2);
  branch=$(echo $bot | cut -d',' -f3); 

  # Handle missing branch
  if [ -z "$branch" ]; then
    branch="main" # Default to 'master' if branch is not specified
  fi

  git clone --branch $branch $source $name;
  cd $name && pip install --no-cache-dir -r requirements.txt && cd ..;
done
