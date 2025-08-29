# Overview
Series of workflows to test for automatic AI translation.
All seven workflows were manually translated from KNIME to Galaxy and 


## General overview on the imaging workflows

**KNWF:** Exported workflow from KNIME (kind of zipped file containing metadata and general description of the workflow

**.ga:** Exported worflow from Galaxy

    - 2025_01_resize_rotate.knwf/.ga
  
Image rescaling (50%) plus different rotation. In KNIME, just 90 degrees right while in Galaxy
six different rotations were included

    - 2025_01_resize_rotate_nested.knwf/.ga

Nested workflow. Three image rescaling (25, 50, 75%) plus different rotation. In KNIME, just 90 degrees right while in Galaxy
six different rotations where included

    - 2025_02_image_conversion.knwf/.ga

Single image conversion to OME-TIFF

    - 2025_02_image_conversion_nested.knwf/.ga

Image conversion to OME-TIFF, JPEG and TIFF

    - 2025_03_2D_spot_detection.knwf/.ga

Workflow for 2D spot detection in fluorescence images plus feature extraction. The .ga workflow is slightly different
and in this case the 1-to-1 translation is not valid. Other tools need to be used in Galaxy to
achieve the same result

    - 2025_04_segmentation_morph_ope.knwf/.ga

Nuclei segmentation workflow with channel extraction, preprocessing (histogram normalization, plus
median filter), Otsu threshold followed by a morphological operation (erosion) on the binary image.
The workflow ends with a connected component analysis and a labeled image as output

    - 2025_04_segmentation_morph_ope_nested.knwf/.ga

Nested nuclei segmentation workflow with channel extraction, preprocessing including two
different filters form comparison (histogram normalization, plus
median filter OR gaussian filter), Otsu threshold followed by a morphological operation (erosion) on the binary image.
The workflow ends with a connected component analysis and a labeled image as output
