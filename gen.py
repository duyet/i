import os
import sys
import jinja2


def scan_images():
    """
    Scan a project for all the files and directories.
    """
    current_dir = os.getcwd()
    projects = {}

    # Scan the image_name is the directory in top level
    # The image_tag is the directory in the image_name directory
    for image_name in os.listdir(current_dir):
        if os.path.isdir(image_name):
            projects[image_name] = []
            for image_tag in os.listdir(image_name):
                check = os.path.join(image_name, image_tag, 'Dockerfile')
                if os.path.isfile(check):
                    projects[image_name].append(image_tag)

    # Filter out the empty image_tags
    projects = {k: v for k, v in projects.items() if v}

    return projects


def get_template():
    """ jinja2 template for Github workflows from string """

    template = """# Generated by gen.py script
# Do not edit this file manually

name: Build and Push
on:
  push:
    branches:
      - master
{% raw %}
env:
  REGISTRY: ghcr.io
  REPO: ${{ github.repository }}
{% endraw %}

jobs:
{%- for image_name, image_tags in images.items() %}
  {{ image_name }}:
    name: Build {{ image_name }}
    runs-on: ubuntu-latest
    strategy:
      matrix:
        tags:
          {%- for image_tag in image_tags %}
          - {{ image_tag }}
          {%- endfor %}
    env:
      IMAGE_NAME: {{ image_name }}
      IMAGE_TAG: '{% raw %}${{ matrix.tags }}{% endraw %}'
    {%- raw %}
    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - uses: dorny/paths-filter@v2
        id: changes
        with:
          filters: |
             src:
              - '${{ env.IMAGE_NAME }}/${{ matrix.tags }}/**'
              - '.github/workflows/ci.yaml'

      - name: Log in to the Container registry
        uses: docker/login-action@f054a8b539a109f9f41c372932f1ae047eff08c9
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Docker Buildx
        if: steps.changes.outputs.src == 'true'
        id: buildx
        uses: docker/setup-buildx-action@v1

      - name: Extract metadata (tags, labels) for Docker
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.REPO }}
          tags: |
            type=raw,value=${{ matrix.tags }}

      - name: Build and push
        if: steps.changes.outputs.src == 'true'
        id: docker_build
        uses: docker/build-push-action@v3
        with:
          context: ${{ github.workspace }}
          file: ./${{ env.IMAGE_NAME }}/${{ env.IMAGE_TAG }}/Dockerfile
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          push: true

      - name: Image digest
        if: steps.changes.outputs.src == 'true'
        run: echo ${{ steps.docker_build.outputs.digest }}
    {%- endraw %}
{% endfor -%}
    """

    return template


def build_workflows(images):
    """ Build the workflows yaml for the images. """

    # Get the jinja2 template
    template = jinja2.Template(get_template())

    # Build the workflows
    workflows = template.render(images=images)

    return workflows


if __name__ == "__main__":
    images = scan_images()
    workflows = build_workflows(images)

    # Dry run option
    if '--dry-run' in sys.argv:
        print(workflows)

    # Help option
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Usage:\n  gen.py [--dry-run | --help]")
        sys.exit(0)

    # Write the workflows to the github workflows directory
    target = ".github/workflows/ci.yaml"
    with open(target, 'w') as f:
        f.write(workflows)
        print("Generated workflows to {}".format(target))
