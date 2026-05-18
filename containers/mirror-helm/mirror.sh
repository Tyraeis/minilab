cd /tmp

curl "$SOURCE?pre-release=false&limit=1" \
  -H 'accept: application/json' -o latest_release.json

version=$(jq -r '.[0].tag_name' latest_release.json)
tarball=$(jq -r '.[0].tarball_url' latest_release.json)
prev_version=$(cat /opt/version)

echo "Latest version: '$version' at $tarball"
echo "Last mirrored version: '$prev_version'"

if [ "$version" != "$prev_version" ]; then
  echo "Mirroring $version"

  curl "$tarball" -o ${version}.tar.gz \
    && gzip -d ${version}.tar.gz \
    && tar xfv ${version}.tar \
    && helm package "$CHART_SUBPATH" \
    && curl --user $USERNAME:$PASSWORD -X POST --upload-file ./garage-*.tgz "$DEST" \
    && echo -n $version >/opt/version
else
  echo "$version is already mirrored"
fi
