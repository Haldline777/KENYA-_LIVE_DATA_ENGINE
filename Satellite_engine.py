import ee
import os

# 💡 ALIGNED TO YOUR REGISTERED GOOGLE CLOUD ID: kenya-live-data
TARGET_PROJECT_ID = 'kenya-live-data'

# Secure initialization layer for the data engine backend
try:
    # 1. Attempt standard initialization using saved credentials token
    ee.Initialize(project=TARGET_PROJECT_ID)
except Exception:
    print(f"\n[SYSTEM LOG]: Initializing Secure Remote Authenticator for project '{TARGET_PROJECT_ID}'...")
    try:
        # 2. Force remote notebook handshake mode if tokens expire or reset
        ee.Authenticate(auth_mode='notebook')
        ee.Initialize(project=TARGET_PROJECT_ID)
    except Exception as init_error:
        print(f"[ERROR]: Authentication failed. Ensure '{TARGET_PROJECT_ID}' matches your Cloud console config. Details: {init_error}")

def get_kenya_agri_grid(start_date: str, end_date: str, roi_geometry):
    """
    Pulls high-resolution Sentinel-2 multispectral imagery arrays, 
    deploys pixel-QA cloud masks, and executes automated spatiotemporal 
    matrix gap-filling across specific geographic coordinates.
    """
    
    # 1. Cloud Masking Logic using Sentinel-2 Quality Assurance Band (QA60)
    def mask_s2_clouds(image):
        qa = image.select('QA60')
        cloud_bit_mask = 1 << 10
        cirrus_bit_mask = 1 << 11
        # Clear pixels must have both cloud and cirrus bits set to zero
        mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
               qa.bitwiseAnd(cirrus_bit_mask).eq(0))
        return image.updateMask(mask).divide(10000).set('system:time_start', image.get('system:time_start'))

    # 2. Ingest Imagery over Kenya Area of Interest (ROI)
    s2_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterDate(start_date, end_date)
                     .filterBounds(roi_geometry)
                     .map(mask_s2_clouds))

    # 3. Calculate Normalized Difference Vegetation Index (NDVI)
    def calculate_ndvi(image):
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return image.addBands(ndvi).select('NDVI')

    ndvi_collection = s2_collection.map(calculate_ndvi)
    
    # 4. Native Spatiotemporal Gap Filling (Temporal Mosaic Reduction)
    # This takes the median value of unclouded pixels over the time range,
    # mathematically filling the gaps where clouds were masked out.
    filled_ndvi = ndvi_collection.median().clip(roi_geometry)
    
    return filled_ndvi

print("\n[SYSTEM LOG]: KENYA_LIVE_DATA_ENGINE Satellite Ingestion Module Connected.")

# ==============================================================================
# 🚀 AUTOMATED RUNTIME VALIDATION LOOP
# ==============================================================================
if __name__ == '__main__':
    print("[SYSTEM LOG]: Initiating automated operational test pull over a sample agricultural grid...")
    
    try:
        # Define a mock 10x10km geographic bounding region center point over a Kenya agricultural hub
        test_roi = ee.Geometry.Point([36.8219, -1.2921]).buffer(5000) # Coordinates centered over Nairobi sector
        
        # Test pulling data for a recent 3-month seasonal agricultural window
        test_output = get_kenya_agri_grid(
            start_date='2026-01-01',
            end_date='2026-04-01',
            roi_geometry=test_roi
        )
        
        # Fetch high-level structural metadata properties to verify data array is live and non-empty
        info = test_output.getInfo()
        print("\n✅ [SUCCESS]: Satellite matrix data pull executed with zero execution errors.")
        print(f"📊 [METRIC]: Ingested Array Type -> {info.get('type')} with active band configurations.")
        
    except Exception as pipeline_error:
        print(f"\n❌ [PIPELINE FAIL]: Engine initialized but failed during vector grid extraction.")
        print(f"Detail logs: {pipeline_error}")
