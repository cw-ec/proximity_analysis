from components import PrepareData

"""
This script contains the call to the data prepper script. This  tool contains the following parameters

Parameters:

    - default_gdb: Path to the default gdb for the project. This should contain at minimum the Indigenous_autouc and bld_p layers.
    - scratch_gdb: Path to a scratch gdb for intermediate files.
    - site_a_path: Path to the Site_A layer.
    - adv_pd_lyr: Path to the adv_pd lyr.
    - site_p_path: Path to the site_p lyr.
    - ia_a_nme: Name for the indig_autoch feature classs in the default gdb. The default value of this parameter is "INDIG_AUTOCH_A".
    - bld_p_nme: Name for the bld_p feature class in the default gdb. The defult value of this parameter is "BUILDING_P".
    - sr: WKID for the projection of all layers. (Layers in a different projection will be reprojected to this WKID). The default value is 4326.

More details on these inputs can be found in the docs

"""

PrepareData(default_gdb=r"C:\proximity_analysis\data\Proximity_ON\Default.gdb",
            scratch_gdb=r"C:\proximity_analysis\data\Proximity_ON\scratch.gdb",
            site_a_path=r"C:\proximity_analysis\data\EGDMP1A.gdb\EGD_MTNC_PD_A",
            adv_pd_path=r"C:\proximity_analysis\data\EGDMP1A.gdb\EGD_MTNC_ADVPD_A",
            site_p_path=r"C:\proximity_analysis\data\site_p.gdb\site_p",
            ia_a_nme= "INDIG_AUTOCH_A_LC",
            bld_p_nme="BUILDING_P_PD_WGS",
            sr=3347
            )
