"""Run spatial vegetation generation with chunked FeatureCollection retrieval.

The generator produces a relatively large web FeatureCollection. Calling
FeatureCollection.getInfo() once can leave the Earth Engine connection open
for too long and fail with RemoteDisconnected. This wrapper keeps the existing
analysis untouched and only changes the client-side retrieval into smaller
requests.
"""
from __future__ import annotations

import time

import ee

from scripts import update_vegetation_spatial as generator


_ORIGINAL_GET_INFO = ee.featurecollection.FeatureCollection.getInfo
_CHUNK_SIZE = 200
_MAX_RETRIES = 4


def _chunked_get_info(self):
    size = int(self.size().getInfo())
    if size <= _CHUNK_SIZE:
        return _ORIGINAL_GET_INFO(self)

    features = []
    for offset in range(0, size, _CHUNK_SIZE):
        count = min(_CHUNK_SIZE, size - offset)
        print(f"Retrieving spatial vegetation cells {offset + 1}-{offset + count} of {size}")
        last_error = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                chunk = self.toList(count, offset).getInfo()
                features.extend(chunk or [])
                break
            except Exception as exc:
                last_error = exc
                print(f"Chunk {offset}-{offset + count} failed (attempt {attempt}/{_MAX_RETRIES}): {exc}")
                if attempt < _MAX_RETRIES:
                    time.sleep(5 * attempt)
        else:
            raise last_error

    return {"type": "FeatureCollection", "features": features}


ee.featurecollection.FeatureCollection.getInfo = _chunked_get_info

if __name__ == "__main__":
    generator.main()
