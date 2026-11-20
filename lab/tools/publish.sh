#!/bin/bash
# Publish: the public tree to the main branch of the public repository, and
# the site built from that tree to its gh-pages branch (GitHub Pages serves
# that branch; lab/plans/2026-11-18-review-and-v1.md step 10).
#
#   bash lab/tools/publish.sh --dry-run   everything except the two pushes
#   bash lab/tools/publish.sh --go        the same, then the two pushes
#
# --go only on the owner's word, every time: it makes things public.
#
# Steps: the tree must be a clean commit that is on origin/main;
# public-export.py writes the public tree (and refuses on embargoed
# material); the site is built from that tree, not from the private one;
# every link of the site is checked; the embargo words are searched for
# once more in everything that would be pushed; then one commit on each
# branch, on top of what the public repository has (no history of the
# private repository, never a forced push). Nothing is pushed if a step
# fails. The prepared repositories stay in ~/vl-publish/<UTC>-<commit> for
# a look before --go.
#
# The commits carry the project's name and address, not a person's
# (GIT_NAME, GIT_EMAIL). PUBLIC=<url or path> for another repository (a test).
set -euo pipefail

mode=${1:-}
case $mode in --dry-run|--go) ;; *) sed -n '2,24p' "$0"; exit 2 ;; esac
REPO=$(cd "$(dirname "$0")/../.." && pwd)
PUBLIC=${PUBLIC:-git@github-verified-libs-public:verified-libs/verified-libs.git}
DOMAIN=${DOMAIN:-verified-libs.org}
GIT_NAME=${GIT_NAME:-verified-libs}
GIT_EMAIL=${GIT_EMAIL:-contact@verified-libs.org}
export PYTHONDONTWRITEBYTECODE=1
cd "$REPO"

[ -z "$(git status --porcelain)" ] || { echo "the tree has uncommitted changes: commit first" >&2; exit 2; }
timeout 60 git fetch -q origin
commit=$(git rev-parse HEAD)
[ "$commit" = "$(git rev-parse origin/main)" ] || { echo "HEAD is not origin/main: push first" >&2; exit 2; }
c12=${commit:0:12}
WORK=$HOME/vl-publish/$(date -u +%Y%m%dT%H%M%SZ)-$c12
mkdir -p "$WORK"

python3 lab/tools/public-export.py "$WORK/tree"
python3 "$WORK/tree/site/build.py" "$WORK/site"
python3 "$WORK/tree/site/check_links.py" "$WORK/site" "$WORK/tree"
echo "$DOMAIN" > "$WORK/site/CNAME"
: > "$WORK/site/.nojekyll"   # the pages are plain files: no Jekyll run

words=$(grep -v '^#' site/embargo.txt | sed '/^[[:space:]]*$/d')
if hits=$(grep -rilF -e "$words" "$WORK/tree" "$WORK/site"); then
    echo "embargoed words in what would be published:" >&2; echo "$hits" >&2; exit 1
fi

prepare() {   # DIR BRANCH CONTENT MESSAGE: one commit with CONTENT on top of the public BRANCH
    local dir=$1 branch=$2 content=$3 msg=$4
    timeout 300 git clone -q "$PUBLIC" "$dir" 2> "$dir.clone.log" || { cat "$dir.clone.log" >&2; exit 1; }
    if git -C "$dir" rev-parse -q --verify "origin/$branch" > /dev/null; then
        git -C "$dir" checkout -q -B "$branch" "origin/$branch"
    else
        git -C "$dir" symbolic-ref HEAD "refs/heads/$branch"
        git -C "$dir" read-tree --empty
    fi
    find "$dir" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
    cp -a "$content/." "$dir/"
    git -C "$dir" add -A
    if git -C "$dir" rev-parse -q --verify HEAD > /dev/null && git -C "$dir" diff --cached --quiet; then
        echo "$branch: no change"
    else
        git -C "$dir" -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q -m "$msg"
        echo "$branch: $(git -C "$dir" show --stat --format='%h %an <%ae> %s' HEAD | sed -n '1p;$p' | tr '\n' ' ')"
    fi
}
prepare "$WORK/main" main "$WORK/tree" "verified-libs, exported from $c12"
prepare "$WORK/pages" gh-pages "$WORK/site" "Site built from $c12"

if [ "$mode" = --dry-run ]; then
    echo "dry run: nothing pushed. Prepared: $WORK/main (branch main), $WORK/pages (branch gh-pages)"
    exit 0
fi
for d in main:main pages:gh-pages; do
    dir=$WORK/${d%%:*}; branch=${d##*:}
    if git -C "$dir" rev-parse -q --verify HEAD > /dev/null; then
        timeout 600 git -C "$dir" push -q origin "$branch"
        echo "pushed $branch to $PUBLIC"
    fi
done
echo "published $c12. First time: in the public repository, Settings > Pages: branch gh-pages, folder / (root); then 'Enforce HTTPS'."
