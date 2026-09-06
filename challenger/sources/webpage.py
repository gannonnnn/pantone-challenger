from challenger.capture.browser import collect_browser_source
from challenger.sources.base import CollectionResult, SourceAdapter


class WebpageAdapter(SourceAdapter):
    def collect(self, source, run_date):
        regions, report = collect_browser_source(source, run_date, self.workdir, self.settings)
        return CollectionResult(source=source, regions=regions, report=report)
