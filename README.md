# proximity_analysis

This repository contains tool designed to automate Proximity Analysis tasks. Currently there is 1 tool available for use.

## Environment Setup

In order to run these tools you are required to have a python environment associated with an active license of ArcGIS Pro.
This will allow you to access arcpy and the arcgis python API both of which are required to run this tool. 

No additional installations or setup are required.

## Tools

### Data Prepper

This tool is designed to prep the data for use in the proximity analysis process. It takes the following parameters.

|  Parameter  |  Type   | Required | Description                                                                                                                                               |
|:-----------:|:-------:|:--------:|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| default_gdb | string  | Required | Path to the default gdb for the project. This should contain at minimum the Indigenous_autouc and bld_p layers                                            |
| scratch_gdb | string  | Required | Path to a scratch gdb for intermediate files                                                                                                              |
| site_a_path | string  | Required | Path to the Site_A layer                                                                                                                                  |
| adv_pd_path | string  | Required | Path to the adv_pd lyr                                                                                                                                    |
| site_p_path | string  | Required | Path to the site_p lyr                                                                                                                                    |
|  ia_a_nme   | string  | Optional | Name for the indig_autoch feature classs in the default gdb. The default value for this parameter is "INDIG_AUTOCH_A"                                     |
|  bld_p_nme  | string  | Optional | Name for the bld_p feature class in the default gdb. The default value for this parameter is "BUILDING_P".                                                |
| out_fc_nme  | String  | Optional | Name for the output feature class. Default value for this parameter is "bld_p_processed".                                                                 |
|     sr      | integer | Optional | WKID for the projection of all layers. (Layers in a different projection will be reprojected to this WKID). The default value for this parameter is 4326. |

Further Documentation to be produced as needed.