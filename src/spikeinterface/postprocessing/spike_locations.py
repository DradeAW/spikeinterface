import numpy as np

from spikeinterface.core.job_tools import _shared_job_kwargs_doc, fix_job_kwargs
from spikeinterface.core.sortingresult import register_result_extension, ResultExtension
from spikeinterface.core.template_tools import get_template_extremum_channel


from spikeinterface.core.node_pipeline import SpikeRetriever, run_node_pipeline


# TODO job_kwargs



class ComputeSpikeLocations(ResultExtension):
    """
    Localize spikes in 2D or 3D with several methods given the template.

    Parameters
    ----------
    sorting_result: SortingResult
        A SortingResult object
    ms_before : float, default: 0.5
        The left window, before a peak, in milliseconds
    ms_after : float, default: 0.5
        The right window, after a peak, in milliseconds
    spike_retriver_kwargs: dict
        A dictionary to control the behavior for getting the maximum channel for each spike
        This dictionary contains:

          * channel_from_template: bool, default: True
              For each spike is the maximum channel computed from template or re estimated at every spikes
              channel_from_template = True is old behavior but less acurate
              channel_from_template = False is slower but more accurate
          * radius_um: float, default: 50
              In case channel_from_template=False, this is the radius to get the true peak
          * peak_sign, default: "neg"
              In case channel_from_template=False, this is the peak sign.
    method : "center_of_mass" | "monopolar_triangulation" | "grid_convolution", default: "center_of_mass"
        The localization method to use
    method_kwargs : dict, default: dict()
        Other kwargs depending on the method.
    outputs : "concatenated" | "by_unit", default: "concatenated"
        The output format
    {}

    Returns
    -------
    spike_locations: np.array or list of dict
        The spike locations.
            - If "concatenated" all locations for all spikes and all units are concatenated
            - If "by_unit", locations are returned as a list (for segments) of dictionaries (for units)    """

    extension_name = "spike_locations"
    depend_on = ["fast_templates|templates", ]
    need_recording = True
    use_nodepipeline = True

    def __init__(self, sorting_result):
        ResultExtension.__init__(self, sorting_result)

        extremum_channel_inds = get_template_extremum_channel(self.sorting_result, outputs="index")
        self.spikes = self.sorting_result.sorting.to_spike_vector(extremum_channel_inds=extremum_channel_inds)

    def _set_params(
        self,
        ms_before=0.5,
        ms_after=0.5,
        spike_retriver_kwargs=None,
        method="center_of_mass",
        method_kwargs={},
    ):  
        spike_retriver_kwargs_ = dict(
            channel_from_template=True,
            radius_um=50,
            peak_sign="neg",
        )
        if spike_retriver_kwargs is not None:
            spike_retriver_kwargs_.update(spike_retriver_kwargs)
        params = dict(
            ms_before=ms_before, ms_after=ms_after, spike_retriver_kwargs=spike_retriver_kwargs_, method=method,
            method_kwargs=method_kwargs
        )
        return params

    def _select_extension_data(self, unit_ids):
        old_unit_ids = self.sorting_result.unit_ids
        unit_inds = np.flatnonzero(np.isin(old_unit_ids, unit_ids))

        spike_mask = np.isin(self.spikes["unit_index"], unit_inds)
        new_spike_locations = self.data["spike_locations"][spike_mask]
        return dict(spike_locations=new_spike_locations)

    def _get_pipeline_nodes(self):
        from spikeinterface.sortingcomponents.peak_localization import get_localization_pipeline_nodes

        recording = self.sorting_result.recording
        sorting = self.sorting_result.sorting
        peak_sign=self.params["spike_retriver_kwargs"]["peak_sign"]
        extremum_channels_indices = get_template_extremum_channel(self.sorting_result, peak_sign=peak_sign, outputs="index")

        retriever = SpikeRetriever(
            recording,
            sorting,
            channel_from_template=True,
            extremum_channel_inds=extremum_channels_indices,
        )
        nodes = get_localization_pipeline_nodes(
            recording, retriever, method=self.params["method"], ms_before=self.params["ms_before"], ms_after=self.params["ms_after"], **self.params["method_kwargs"]
        )
        return nodes

    def _run(self, **job_kwargs):
        # TODO later gather to disk when format="binary_folder"
        job_kwargs = fix_job_kwargs(job_kwargs)
        nodes = self.get_pipeline_nodes()
        spike_locations = run_node_pipeline(
            self.sorting_result.recording, nodes, job_kwargs=job_kwargs, job_name="spike_locations", gather_mode="memory"
        )
        self.data["spike_locations"] = spike_locations

    # def get_data(self, outputs="concatenated"):
    #     """
    #     Get computed spike locations

    #     Parameters
    #     ----------
    #     outputs : "concatenated" | "by_unit", default: "concatenated"
    #         The output format

    #     Returns
    #     -------
    #     spike_locations : np.array or dict
    #         The spike locations as a structured array (outputs="concatenated") or
    #         as a dict with units as key and spike locations as values.
    #     """
    #     we = self.sorting_result
    #     sorting = we.sorting

    #     if outputs == "concatenated":
    #         return self._extension_data["spike_locations"]

    #     elif outputs == "by_unit":
    #         locations_by_unit = []
    #         for segment_index in range(self.sorting_result.get_num_segments()):
    #             i0 = np.searchsorted(self.spikes["segment_index"], segment_index, side="left")
    #             i1 = np.searchsorted(self.spikes["segment_index"], segment_index, side="right")
    #             spikes = self.spikes[i0:i1]
    #             locations = self._extension_data["spike_locations"][i0:i1]

    #             locations_by_unit.append({})
    #             for unit_ind, unit_id in enumerate(sorting.unit_ids):
    #                 mask = spikes["unit_index"] == unit_ind
    #                 locations_by_unit[segment_index][unit_id] = locations[mask]
    #         return locations_by_unit


ComputeSpikeLocations.__doc__.format(_shared_job_kwargs_doc)

register_result_extension(ComputeSpikeLocations)
compute_spike_locations = ComputeSpikeLocations.function_factory()
