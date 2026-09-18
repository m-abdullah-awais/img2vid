r"""Where the API keeps everything, decided once per server.

Storage defaults to backend\storage and the runtime to backend\runtime, the
same folders the engine uses. Both can be pointed elsewhere, which is how the
tests run against a throwaway folder under temp\ and how they simulate a
machine where the speech engine was never installed.

    storage\projects\<id>\    project.json plus audio\ images\ transcript\ videos\
    storage\work\             working files: api\ (job history), uploads\,
                              renders\, thumbs\, renames\
    storage\trash\<trashId>\  one removed item plus its meta.json

The scripts in backend\cli\ always write their own working files (encoder
choice, transcription cache, job folders) to i2v.paths.WORK, because the engine
fixes that path itself. With the default storage that is the same folder as
`work` here. `engine_work` names it, so the encoder cache is read from where
the engine really writes it.
"""

import os

from i2v import paths


class Config:
    def __init__(self, storage=None, runtime=None):
        self.storage = os.path.abspath(storage or paths.STORAGE)
        self.runtime = os.path.abspath(runtime or paths.RUNTIME)

    @property
    def projects(self):
        return os.path.join(self.storage, "projects")

    @property
    def work(self):
        return os.path.join(self.storage, "work")

    @property
    def trash(self):
        return os.path.join(self.storage, "trash")

    @property
    def api(self):
        return os.path.join(self.work, "api")

    @property
    def jobs_file(self):
        return os.path.join(self.api, "jobs.json")

    @property
    def uploads(self):
        return os.path.join(self.work, "uploads")

    @property
    def renders(self):
        return os.path.join(self.work, "renders")

    @property
    def thumbs(self):
        return os.path.join(self.work, "thumbs")

    @property
    def renames(self):
        return os.path.join(self.work, "renames")

    @property
    def bin(self):
        return os.path.join(self.runtime, "bin")

    @property
    def node(self):
        return os.path.join(self.runtime, "node", "node.exe" if os.name == "nt" else "node")

    # Fixed by the engine, see the module docstring.
    engine_work = paths.WORK
    cli = os.path.join(paths.BACKEND, "cli")

    def script(self, name):
        return os.path.join(self.cli, name)

    def ensure(self):
        for folder in (self.projects, self.trash, self.api, self.uploads,
                       self.renders, self.thumbs, self.renames):
            os.makedirs(folder, exist_ok=True)
