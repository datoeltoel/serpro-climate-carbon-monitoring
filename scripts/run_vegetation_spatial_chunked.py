"""Run spatial vegetation generation with bounded Earth Engine retrieval.

The spatial result is a computed FeatureCollection. Calling ``size().getInfo()``
first forces Earth Engine to evaluate the entire collection before we can start
retrieving features, which can exceed the synchronous computation timeout.
This wrapper therefore paginates directly with ``toList`` and stops when a
page is empty. It also keeps each response deliberately small.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import ee

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import update_vegetation_spatial as generator


_CHUNK_SIZE = 100
_MAX_RETRIES = 4
_MAX_FEATURES = 20000


def _chunked_get_info(self):
    """Retrieve a computed FeatureCollection without evaluating ``size()``."""
    features = []
    offset = 0

    while offset < _MAX_FEATURES:
        count = min(_CHUNK_SIZE, _MAX_FEATURES - offset)
        print(f"Retrieving spatial vegetation cells {offset + 1}-{offset + count}")
        last_error = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                chunk = self.toList(count, offset).getInfo() or []
                if not chunk:
                    print(f"No more spatial vegetation cells after {len(features)} cells.")
                    return {"type": "FeatureCollection", "features": features}

                features.extend(chunk)
                offset += len(chunk)
                if len(chunk) < count:
                    print(f"Retrieved final page; total cells={len(features)}")
                    return {"type": "FeatureCollection", "features": features}
                break
            except Exception as exc:
                last_error = exc
                print(
                    f"Page offset={offset} failed (attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )
                if attempt < _MAX_RETRIES:
                    time.sleep(5 * attempt)
        else:
            raise last_error

    raise RuntimeError(
        f"Spatial vegetation output exceeded the safety limit of {_MAX_FEATURES} cells. "
        "Increase the display grid size before generating a larger GeoJSON."
    )


ee.featurecollection.FeatureCollection.getInfo = _chunked_get_info

if __name__ == "__main__":
    generator.main()
