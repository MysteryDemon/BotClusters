for bot in $(cat config.json | jq -r 'to_entries[] | "\(.key),\(.value.source),\(.value.branch)"'); do
  name=$(echo $bot | cut -d',' -f1);
  source=$(echo $bot | cut -d',' -f2);
  branch=$(echo $bot | cut -d',' -f3);

  # Handle missing branch
  if [ -z "$branch" ]; then
    branch="master" 
  fi

  # Fetch latest commit
  git clone --branch $branch $source $name
  cd $name
  git fetch origin
  git checkout $branch
  pip install --no-cache-dir -r requirements.txt 
  cd ..
done
