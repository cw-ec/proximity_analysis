import os, sys, logging
import pandas as pd
import datetime
from arcgis import GeoAccessor, GeoSeriesAccessor
from arcpy import env, Geometry, ListFields, ListFeatureClasses, ListDatasets, Exists
from arcpy.da import UpdateCursor
from arcpy.analysis import Identity, SpatialJoin
from arcpy.management import SelectLayerByLocation, SelectLayerByAttribute, MakeFeatureLayer, GetCount, FeatureToPoint, \
    Append, AddField, DeleteField, CreateFileGDB
from arcpy.conversion import ExportFeatures

env.overwriteOutput = True  # Need this to overwrite outputs without failing


class PrepareData:
    @staticmethod
    def logging_setup(log_dir=".\\logs") -> logging.getLogger():
        """Sets up logging takes one parameter to set a directory for the output log file"""

        def create_dir(path: str) -> None:
            """Check if directory exists and if it doesn't create it."""
            if not os.path.exists(path):
                os.makedirs(path)

        create_dir(log_dir)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(os.path.join(log_dir, f"{datetime.datetime.today().strftime('%Y-%m-%d')}.log"),
                                    mode='a',),
                logging.StreamHandler(sys.stdout)
            ],
            datefmt="[%Y-%m-%d %H:%M:%S]"  # Tidy's up datetime format
        )
        return logging.getLogger()

    @staticmethod
    def is_valid(default_gdb, scratch_gdb, site_a_path, site_p_path, adv_pd_path, ia_a_nme, out_fc_nme, sr) -> None:
        """Validates input parameters and ensures that they are valid before processing the data"""
        if not Exists(default_gdb):
            raise Exception(f"Parameter default_gdb: Does not exist and should exist before processing begins")
        if not Exists(site_a_path):
            raise Exception(
                f"Parameter site_a_path: Must be a valid link to the data and must exist before processing begins.")
        if not Exists(site_p_path):
            raise Exception(
                f"Parameter site_p_path: Must be a valid link to the data and must exist before processing begins.")
        if not Exists(adv_pd_path):
            raise Exception(
                f"Parameter adv_pd_path: Must be a valid link to the data and must exist before processing begins.")
        if not isinstance(ia_a_nme, str):
            raise Exception("Parameter ia_a_nme: Must be of type string.")
        if not isinstance(scratch_gdb, str):
            raise Exception(
                f" Parameter 'scratch_gdb' is of type {type(scratch_gdb)}. This parameter must be a string.")
        if not isinstance(out_fc_nme, str):
            raise Exception("Parameter out_fc_nme: Must be of type string.")
        if not isinstance(sr, int):
            raise Exception(
                f"Parameter sr: Must be an integer matching a projections WKID. Is currently type: {type(sr)}")

    def add_site_id(self, target_lyr, site_lyr, non_ess_fields: list[str], bldp_lyr, orig_sdf, fld_nme: str,
                    out_fld_nme: str, scratch_gdb_path: str, scratch_fc_nme='scratch',
                    link_fld='PLACE_ID') -> GeoAccessor:
        """Adds the site id field to the target layer from the site layer and names it according to the out field name"""

        scratch_fc_path = os.path.join(scratch_gdb_path, scratch_fc_nme)
        temp_id = "temp_id"

        # Create temp ID field to prevent duplication errors
        AddField(target_lyr, temp_id, 'LONG')
        with UpdateCursor(target_lyr, [temp_id]) as cursor:
            row_int = 1
            for row in cursor:
                row[0] = row_int
                row_int += 1
                cursor.updateRow(row)

        # If the field(s) we're working with already exist in the dataset delete it
        if Exists(scratch_fc_path):
            for fld in [fld_nme, out_fld_nme]:
                if fld in [f.name for f in ListFields(scratch_fc_path)]:
                    self.logger.info(f"{fld} already in target layer. Deleting existing field")
                    DeleteField(scratch_fc_path, fld_nme)

        Identity(target_lyr, site_lyr, scratch_fc_path)  # Adds the fields site id field from site_a to the target layer
        DeleteField(in_table=scratch_fc_path,
                    drop_field=non_ess_fields,
                    method="DELETE_FIELDS")  # Delete non essential fields from the result

        # Identity explodes multiparts and parts can have diff site_ids. find part with highest point count and use the site associated with that part for that community (all parts)
        SpatialJoin(scratch_fc_path, bldp_lyr,
                    f"{scratch_fc_path}_2")  # Used because we jet a join_count field for the points in that polygon
        sdf = GeoAccessor.from_featureclass(f"{scratch_fc_path}_2",
                                            sr=self.sr)  # convert the results to a dataframe because its easier

        # Keep only the parts that have the highest count if they are duplicated
        sdf = sdf.sort_values(by='Join_Count', ascending=False).drop_duplicates(subset=temp_id, keep='first')

        if fld_nme not in sdf.columns.tolist():
            self.logger.info(fld_nme + " not in the output dataframe error")
            self.logger.info(sdf.columns)
            sys.exit()

        sdf.rename(columns={fld_nme: out_fld_nme}, inplace=True)

        if out_fld_nme not in sdf.columns.tolist():
            self.logger.info(out_fld_nme + " not in the output dataframe error")
            sys.exit()

        # Merge the linked site_id field to the original data
        orig_sdf = orig_sdf.merge(sdf[[link_fld, out_fld_nme]],
                                  on=link_fld)

        return orig_sdf

    def check_site_id_exists(self, in_ids: list[int], site_p_sdf, site_fld='SITE_ID') -> list:
        """Checks to see if the input site ids are in the site_p layer and returns a list of those ids if found"""

        return [f for f in in_ids if f not in site_p_sdf[site_fld].tolist()]

    def step_1(self):
        """Identify indigenous communities without points in bld_p and add one (centroid) to the layer for the purpose of this analysis"""

        # Use select by location to Identify polygons in the indigneous layer that have no blding_p points

        # In the indigenous layer select all those polygons that intersect a point
        SelectLayerByLocation('ia_a', "INTERSECT", 'bld_p')
        # Swap that selection so that we get those that have no points
        SelectLayerByAttribute('ia_a', "SWITCH_SELECTION")

        no_points_cnt = int(GetCount(self.ia_flyr)[0])  # Count of all polygons that have no points in them

        self.logger.info(f"Number of indigneous polygons with no BLDING_P points = {no_points_cnt}")

        if no_points_cnt > 0:  # If the no points count is greater than 0 add the centroid of those polygons to the blding p layer

            centroids_path = os.path.join(self.scratch_gdb, 'ia_centroids')  # Path to our centroids layer
            FeatureToPoint(self.ia_flyr, centroids_path, "INSIDE")

            self.bld_p_nme = f"{self.bld_p_nme}_ap"
            self.bld_p_pth = os.path.join(self.scratch_gdb, self.bld_p_nme)
            ExportFeatures(self.bld_p_flyr, self.bld_p_pth)

            # Append the new points to the bld_p_lyr
            Append(inputs=[centroids_path], target=self.bld_p_pth, schema_type="NO_TEST")
            self.bld_p_flyr = MakeFeatureLayer(self.bld_p_pth, 'bld_p')  # Update the bld_p feature layer

    def step_2(self):
        """Associate the pd and adv site data with the point in each polygon"""

        # Add the pd fields to the indigenous layer
        self.indig_sdf = self.add_site_id(target_lyr=self.ia_a_pth,
                                          site_lyr=self.site_a_pth,
                                          orig_sdf=self.indig_sdf,
                                          non_ess_fields=self.site_a_fields,
                                          bldp_lyr=self.bld_p_flyr,
                                          fld_nme='PD_Site_ID',
                                          out_fld_nme=self.pd_sid_fld_nme,
                                          scratch_gdb_path=self.scratch_gdb)  # FOR PD SITE_ID

        self.indig_sdf = self.add_site_id(target_lyr=self.ia_a_pth,
                                          site_lyr=self.adv_pd_pth,
                                          orig_sdf=self.indig_sdf,
                                          non_ess_fields=self.advpd_fields,
                                          bldp_lyr=self.bld_p_flyr,
                                          fld_nme='ADVPD_Site_ID',
                                          out_fld_nme=self.adv_sid_fld_nme,
                                          scratch_gdb_path=self.scratch_gdb)  # FOR ADVPD_SITE_ID

    def step_3(self):
        """Test to see if the matched id fields are in the pd layer and note any that are not present"""

        pd_site_id = self.indig_sdf[self.pd_sid_fld_nme].to_list()
        adv_site_id = self.indig_sdf[self.adv_sid_fld_nme].to_list()

        site_p_sdf = GeoAccessor.from_featureclass(self.site_p_pth)

        pd_missing = self.check_site_id_exists(pd_site_id, site_p_sdf)
        adv_missing = self.check_site_id_exists(adv_site_id, site_p_sdf)

        self.logger.info(f"Site_P points missing from matched site_ids (count): PDs: {len(pd_missing)}, ADVs:{len(adv_missing)}")
        if len(pd_missing) > 0:
            self.logger.info(f"Missing PD site_ids: {pd_missing}")
        if len(adv_missing) > 0:
            self.logger.info(f"Missing ADV site_ids: {adv_missing}")

    def step_4(self):
        """Join the site_id's from the indigenous layers to the building_p layer"""
        bld_p_sdf = GeoAccessor.from_featureclass(self.bld_p_pth, sr=self.sr)

        # Perform the spatial join
        bld_p_sdf_joined = bld_p_sdf.spatial.join(self.indig_sdf[[self.adv_sid_fld_nme, self.pd_sid_fld_nme, "SHAPE"]],
                                                  op=self.spatial_relationship)
        bld_p_sdf_joined.drop(columns=['index_right'], inplace=True)

        bld_p_sdf_joined.spatial.to_featureclass(os.path.join(scratch_gdb, self.out_fc_nme), overwrite=True)

    def __init__(self, default_gdb: str, scratch_gdb: str, site_a_path: str, adv_pd_path: str, site_p_path: str,
                 ia_a_nme="INDIG_AUTOCH_A", bld_p_nme="BUILDING_P", out_fc_nme="bld_p_processed", sr=4326) -> None:

        self.logger = self.logging_setup()
        self.logger.info("Starting Data Prep")
        self.logger.info('Validating Inputs')
        self.is_valid(default_gdb, scratch_gdb, site_a_path, site_p_path, adv_pd_path, ia_a_nme, out_fc_nme, sr)

        if not Exists(scratch_gdb):
            self.logger.info("Creating scratch gdb")
            path_elements = os.path.split(scratch_gdb)
            CreateFileGDB(path_elements[0], path_elements[1])

        # Set other parameters
        self.ia_a_nme = ia_a_nme  # Name of the IND_AUT_A layer
        self.bld_p_nme = bld_p_nme  # Name of the building p layer
        self.spatial_relationship = 'intersects'

        self.pd_sid_fld_nme = "AUTO_PD_SITE_ID"
        self.adv_sid_fld_nme = "AUTO_ADV_SITE_ID"
        self.out_fc_nme = out_fc_nme

        # Set the data parameters
        self.default_gdb = default_gdb
        self.scratch_gdb = scratch_gdb
        self.site_a_pth = site_a_path
        self.site_p_pth = site_p_path
        self.adv_pd_pth = adv_pd_path
        self.sr = sr
        self.ia_a_pth = os.path.join(self.default_gdb, f"{self.ia_a_nme}")
        self.bld_p_pth = os.path.join(self.default_gdb, f"{self.bld_p_nme}")
        self.indig_sdf = GeoAccessor.from_featureclass(self.ia_a_pth, sr=self.sr)

        # Get a list of all site a fields to drop exclude essential fields (cannot be deleted) and the field we want to keep (SITE_ID)
        self.site_a_fields = [f.name for f in ListFields(self.site_a_pth) if
                              f.name not in ["SHAPE.AREA", "SHAPE.LEN", "SITE_ID", "OBJECTID", 'Shape', 'SHAPE',
                                             'Shape_Area', 'Shape_Length']]
        self.advpd_fields = [f.name for f in ListFields(self.site_a_pth) if
                             f.name not in ["SHAPE.AREA", "SHAPE.LEN", "SITE_ID", "OBJECTID", 'Shape', 'SHAPE',
                                            'Shape_Area', 'Shape_Length']]

        # Make the key layers into feature layers
        self.ia_flyr = MakeFeatureLayer(self.ia_a_pth, "ia_a")
        self.bld_p_flyr = MakeFeatureLayer(self.bld_p_pth, 'bld_p')

        # run the process
        self.logger.info(
            "Running step 1: Identify indigenous communities without points in bld_p and add one (centroid) to the layer for the purpose of this analysis")
        self.step_1()

        self.logger.info("Running step 2: Associate the pd and adv site data with the point in each polygon")
        self.step_2()

        self.logger.info(
            "Running step 3: Test to see if the matched id fields are in the pd layer and note any that are not present")
        self.step_3()

        self.logger.info("Running step 4: Join the site_id's from the indigenous layers to the building_p layer")
        self.step_4()

        self.logger.info("Data Prep Complete!")

# Here for testing purposes only
if __name__ == "__main__":
    default_gdb = r"C:\proximity_analysis\data\Proximity_ON\Default.gdb"
    scratch_gdb = r"C:\proximity_analysis\data\Proximity_ON\scratch.gdb"

    indig_autoch_nme = "INDIG_AUTOCH_A_LC"
    bld_p_nme = "BUILDING_P_PD_WGS"
    wkid = 3347

    site_a_pth = r"C:\proximity_analysis\data\EGDMP1A.gdb\EGD_MTNC_PD_A"
    adv_pd_path = r"C:\proximity_analysis\data\EGDMP1A.gdb\EGD_MTNC_ADVPD_A"
    site_p_pth = r"C:\proximity_analysis\data\site_p.gdb\site_p"

    PrepareData(default_gdb=default_gdb,
                scratch_gdb=scratch_gdb,
                site_a_path=site_a_pth,
                adv_pd_path=adv_pd_path,
                site_p_path=site_p_pth,
                ia_a_nme= indig_autoch_nme,
                bld_p_nme=bld_p_nme,
                sr=wkid)