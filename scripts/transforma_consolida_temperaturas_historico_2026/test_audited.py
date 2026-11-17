import unittest
import pandas as pd
import numpy as np
import main as base
import audited

class GapPolicyTests(unittest.TestCase):
    def zone(self, gap, right=12.):
        dates=pd.date_range('2025-05-01',periods=gap+2,freq='h')
        return pd.DataFrame(dict(ds=dates,temperatura_c=[0.]+[np.nan]*gap+[right],codigo_lugar='MEL',id_lugar=2,lugar='Melipilla',nombre_maestro='melipilla',condicion='calido',latitud=-33.,longitud=-71.,observaciones_validas=[1]+[0]*gap+[1],observaciones_total=[1]+[0]*gap+[1]))

    def test_six_hour_gap_is_entirely_interpolated(self):
        result=base.complete_and_impute_zone(self.zone(6),climatology_mode='none')
        self.assertEqual(result.tipo_dato.tolist(),['observado']+['interpolado']*6+['observado'])
        self.assertAlmostEqual(result.temperatura_c.iloc[3],36/7)

    def test_seven_hour_gap_has_no_partial_interpolation(self):
        result=base.complete_and_impute_zone(self.zone(7),climatology_mode='none')
        self.assertEqual(result.temperatura_c.isna().sum(),7)
        self.assertTrue(result.hueco_original_horas.iloc[1:-1].eq(7).all())

    def test_cutoff_removes_future_endpoint_and_donors(self):
        z=self.zone(2,100.)
        result=base.complete_and_impute_zone(z,climatology_mode='cutoff',cutoff=z.ds.iloc[2],end=z.ds.iloc[2])
        self.assertTrue(result.temperatura_c.eq(0).all())
        self.assertEqual(result.donantes_total.iloc[0],1)
        self.assertEqual(result.ds.max(),z.ds.iloc[2])

    def test_cutoff_required_and_future_horizon_rejected(self):
        with self.assertRaises(ValueError): base.complete_and_impute_zone(self.zone(1),climatology_mode='cutoff')
        with self.assertRaises(ValueError): base.complete_and_impute_zone(self.zone(1),cutoff=pd.Timestamp('2025-05-01'),end=pd.Timestamp('2025-05-02'))
        with self.assertRaisesRegex(ValueError,'no observations'):
            base.complete_and_impute_zone(self.zone(1),climatology_mode='cutoff',cutoff=pd.Timestamp('2025-04-30'))

    def test_edge_gap_not_interpolated(self):
        result=base.complete_and_impute_zone(self.zone(1),climatology_mode='none',end=pd.Timestamp('2025-05-01 04:00'))
        self.assertTrue(result.temperatura_c.iloc[-2:].isna().all())

    def test_synthetic_values_are_not_climate_donors(self):
        result=base.complete_and_impute_zone(self.zone(6))
        self.assertTrue(result.donantes_total.eq(2).all())

    def test_single_key_climatology_mapping(self):
        f=pd.DataFrame(dict(hora=[3,4],temperatura_c=[np.nan,np.nan],metodo_imputacion=[None,None],donantes_metodo_n=[0,0],donantes_anios=['','']))
        base.fill_with_mapping(f,pd.Series({3:8.}),['hora'],'mediana_horaria_zona',pd.Series({3:2}),pd.Series({3:'2024|2025'}))
        self.assertEqual(f.temperatura_c.iloc[0],8.)
        self.assertTrue(pd.isna(f.temperatura_c.iloc[1]))
        self.assertEqual(f.donantes_metodo_n.iloc[0],2)
        self.assertEqual(f.donantes_anios.iloc[0],'2024|2025')

class SourcePolicyTests(unittest.TestCase):
    def test_exact_copies_do_not_weight_hourly_mean(self):
        d=pd.DataFrame(dict(codigo_lugar=['SAR']*3,ds=pd.to_datetime(['2025-05-01']*3),ds_original=pd.to_datetime(['2025-05-01 00:01','2025-05-01 00:01','2025-05-01 00:11']),temperatura_c=[2.,2.,8.],rechazo=['']*3,id_registro=['kor::2','reg::2','kor::3'],fuente=['fia']*3,hoja=['kor','reg','kor']))
        h=audited.source_hourly(d)
        self.assertEqual(h.temperatura_c.iloc[0],5.)
        self.assertEqual(h.observaciones_validas.iloc[0],2)
        self.assertEqual(h.observaciones_total.iloc[0],3)
        self.assertIn('reg::2',h.registros_fuente.iloc[0])

    def test_history_wins_overlap_and_fia_fills_new_hour(self):
        def f(times,temps,name):
            return pd.DataFrame(dict(codigo_lugar='MEL',ds=pd.to_datetime(times,format='mixed'),temperatura_c=temps,fuente=name))
        old=f(['2025-05-01'],[10.],'history')
        empty=old.iloc[:0]
        fia=f(['2025-05-01','2025-05-01 01:00'],[99.,5.],'fia')
        result=audited.merge_sources(old,empty,empty,fia,base.read_lugar_master())
        self.assertEqual(result.temperatura_c.tolist(),[10.,5.])
        self.assertEqual(result.fuente.tolist(),['history','fia'])

    def test_invalid_replacements_do_not_erase_valid_older_measurements(self):
        d=pd.DataFrame(dict(codigo_lugar=['MEL'],ds=pd.to_datetime(['2026-01-01']),ds_original=pd.to_datetime(['2026-01-01']),temperatura_c=[np.nan],rechazo=['temperatura_no_numerica'],id_registro=['v2::2'],fuente=['v2'],hoja=['Melipilla']))
        self.assertTrue(audited.source_hourly(d).empty)

    def test_fia_2024_is_combined_without_replacing_existing_observations(self):
        old=pd.DataFrame(dict(codigo_lugar=['MEL'],ds=pd.to_datetime(['2024-01-01']),temperatura_c=[10.],fuente=['history']))
        fia=pd.DataFrame(dict(codigo_lugar=['MEL','MEL'],ds=pd.to_datetime(['2024-01-01','2024-01-02']),temperatura_c=[99.,5.],fuente=['FIA 2024']*2))
        result=audited.merge_sources(old,old.iloc[:0],old.iloc[:0],old.iloc[:0],base.read_lugar_master(),fia_2024=fia)
        self.assertEqual(result.temperatura_c.tolist(),[10.,5.])
        self.assertEqual(result.fuente.tolist(),['history','FIA 2024'])

    def test_fia_2024_detail_only_fills_hours_missing_from_global(self):
        d=pd.DataFrame(dict(codigo_lugar=['MEL']*3,ds=pd.to_datetime(['2024-05-01','2024-05-01','2024-05-02']),ds_original=pd.to_datetime(['2024-05-01','2024-05-01','2024-05-02']),temperatura_c=[2.,20.,8.],rechazo=['']*3,id_registro=['global::2','detail::2','detail::3'],fuente=[audited.FIA_2024.name]*3,hoja=['Global','T Melipilla','T Melipilla']))
        h=audited.source_hourly(d)
        self.assertEqual(h.temperatura_c.tolist(),[2.,8.])
        self.assertEqual(h.observaciones_validas.tolist(),[1,1])

if __name__=='__main__': unittest.main()
