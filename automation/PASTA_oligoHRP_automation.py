from opentrons import protocol_api
import json
import math

metadata = {
    'protocolName': '2samples_16cycles',
    'author': 'Hendrik A. Michel',
    'description': 'Protocol for automated PASTA oligo-HRP application for up to 2 samples and up to 16 cycles.',
    'apiLevel': '2.7'
}


#################### MODIFIABLE RUN PARAMETERS #########################

# !!! IMPORTANT !!! Leave only the appropriate lines below uncommented
par2_type= 'omni_stainer_c12_cslps' # Use this for Parhelia OmniStainer for coverslips
par2_type= 'omni_stainer_s12_slides' # Use this for Parhelia OmniStainer for slides

# !!! IMPORTANT !!! Leave only the appropriate lines below uncommented
wellslist = ['A2'] # 1 sample - max 32 cycles
wellslist = ['A2', 'A3']  # 2 samples - max 16 cycles
wellslist = ['A2', 'A3', 'A4'] # 3 samples - max 8 cycles
wellslist = ['A2', 'A3', 'A4', 'A5'] # 4 samples - max 8 cycles


PASTA_cycles = 12 # Specify the number of cycles where each cycle amplifies one marker at a time


Tyr_dilution_lib = {# Specify the dilution factor of your PASTA oligos for each cycle for each sample. 
                    # 50 = 1:50 dilution such as 5 µM staining with 250 µM stock solution.
    # Cycles 1-8: Valid for all configurations (1, 2, 3, or 4 samples)
    1:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    2:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    3:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    4:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    5:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    6:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    7:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    8:  {'A2': 50, 'A3': 50, 'A4': 50, 'A5': 50},
    
    # Cycles 9-16: Valid for 1 or 2 sample configurations only
    9:  {'A2': 50, 'A3': 50},
    10: {'A2': 50, 'A3': 50},
    11: {'A2': 50, 'A3': 50},
    12: {'A2': 50, 'A3': 50},
    13: {'A2': 50, 'A3': 50},
    14: {'A2': 50, 'A3': 50},
    15: {'A2': 50, 'A3': 50},
    16: {'A2': 50, 'A3': 50},
    
    # Cycles 17-32: Valid for 1 sample configuration only
    17: {'A2': 50},
    18: {'A2': 50},
    19: {'A2': 50},
    20: {'A2': 50},
    21: {'A2': 50},
    22: {'A2': 50},
    23: {'A2': 50},
    24: {'A2': 50},
    25: {'A2': 50},
    26: {'A2': 50},
    27: {'A2': 50},
    28: {'A2': 50},
    29: {'A2': 50},
    30: {'A2': 50},
    31: {'A2': 50},
    32: {'A2': 50},
}

hydration_time = 6 # Specify how long (in hours) the OT-2 should hydrate the tissue after final PASTA incubation. Do not exceed 24 hours.


#Creating a dummy class
class Object:
    pass

#################### LABWARE LAYOUT ON DECK #########################
pipette_300_location='right'
pipette_300_GEN = 'GEN2'

labwarePositions = Object()
labwarePositions.buffers_reservoir_1 = 1
labwarePositions.buffers_reservoir_2 = 3
labwarePositions.reagent_plate = 6
labwarePositions.par2 = 2
labwarePositions.tiprack_300_1 = 4
labwarePositions.tiprack_300_2 = 5
labwarePositions.tiprack_300_3 = 7
labwarePositions.tiprack_300_4 = 8
labwarePositions.tiprack_300_5 = 9
labwarePositions.tiprack_300_6 = 10
labwarePositions.tiprack_300_7 = 11


####################GENERAL SETUP################################

stats = Object()
stats.volume = 0
debug = False

####################FIXED RUN PARAMETERS#########################
## Experimentally optimized flow rates
### Default volumes for washes (in ul)
wash_volume = 200
DMSO_volume = 200
extra_bottom_gap=0

default_flow_rate = 30
well_flow_rate = 5
sample_flow_rate = 0.25
DMSO_flow_rate = 0.1

## Cycle-aware logic

num_samples = len(wellslist)

# Define cycle logic based on number of samples
if num_samples == 1:
    CODEX_change_interval = 4   # New CODEX every 4 cycles
    Strip_change_interval = 8   # New Strip every 8 cycles
    sample_spacing = 0          # Only 1 sample, no horizontal spacing
    cycle_period = 8            # Cycle period for well rotation
    cycle_offset = 3            # Move 3 columns every 8 cycles
elif num_samples == 2:
    CODEX_change_interval = 2
    Strip_change_interval = 4
    sample_spacing = 6          # 6 columns between samples
    cycle_period = 8
    cycle_offset = 3
elif num_samples in [3, 4]:
    CODEX_change_interval = 1   # New CODEX every cycle
    Strip_change_interval = 2   # New Strip every 2 cycles
    sample_spacing = 3          # 3 columns between samples
    cycle_period = float('inf') # Never change (use inf so division by it = 0)
    cycle_offset = 0


####################! FUNCTIONS - DO NOT MODIFY !######################### 
def washSamples(pipette, sourceSolutionWell, samples, volume, num_repeats=1, disp_rate = sample_flow_rate, dispense_bottom_gap=extra_bottom_gap, keep_tip = False):
    """
    Wash sample chambers by aspirating from a source well and dispensing into samples.
    
    Repeatedly aspirates solution from a source well and dispenses it into specified
    sample chambers. Includes blow-out step for complete aspiration after each cycle.
    
    Parameters
    ----------
    pipette : Pipette
        The pipette instrument to use for aspiration and dispensing.
    sourceSolutionWell : Well
        The well containing the wash solution to aspirate from.
    samples : Well or list of Well
        Sample chamber(s) to dispense wash solution into. Can be a single Well
        or an iterable of Wells.
    volume : float
        Volume in microliters to aspirate and dispense per sample per repeat.
    num_repeats : int, optional
        Number of times to repeat the wash cycle for each sample. Default is 1.
    disp_rate : float, optional
        Dispense flow rate in µL/s. Default is `sample_flow_rate`.
    dispense_bottom_gap : float, optional
        Distance in mm above the well bottom to dispense at. Default is `extra_bottom_gap`.
    keep_tip : bool, optional
        If True, keep the tip on the pipette after completion. If False, drop tip.
        Default is False.
    
    Returns
    -------
    None
    
    Notes
    -----
    - Automatically picks up a tip if the pipette does not have one.
    - Uses `well_flow_rate` for aspiration from source well.
    - Blow-out is performed at the source well top (-5mm) after each dispense.
    
    Examples
    --------
    >>> washSamples(pipette_300, buffer_well, sample_chambers, 200, 2)
    >>> washSamples(pipette_300, strip_buffer, sample_chambers, 200, 3, 
    ...             disp_rate=0.1, keep_tip=True)
    """
   
    try:
        iter(samples)
        #print('samples are iterable')
    except TypeError:
        #print('samples arent iterable')
        samples = [samples]

    if not pipette.has_tip:
        pipette.pick_up_tip()


    for i in range(0, num_repeats):
        print ("Iteration:"+ str(i))
        for s in samples:
            print(s)
            print ("Washing sample:" + str(s))
            pipette.aspirate(volume, sourceSolutionWell, rate=well_flow_rate)
            pipette.dispense(volume, s.bottom(dispense_bottom_gap), rate=disp_rate)
            pipette.blow_out(sourceSolutionWell.top(-5))

    if not keep_tip: pipette.drop_tip()
    
def apply_buffer(pipette, sourceSolutionWell, samples, volume, dispense_bottom_gap=extra_bottom_gap, keep_tip = False):
    """
    Apply buffer solution to sample chambers.
    
    Aspirates buffer from a source well and dispenses it into specified sample chambers.
    Similar to washSamples but performs a single application cycle.
    
    Parameters
    ----------
    pipette : Pipette
        The pipette instrument to use for aspiration and dispensing.
    sourceSolutionWell : Well
        The well containing the buffer solution to aspirate from.
    samples : Well or list of Well
        Sample chamber(s) to apply buffer to. Can be a single Well or an iterable
        of Wells.
    volume : float
        Volume in microliters to aspirate and dispense per sample.
    dispense_bottom_gap : float, optional
        Distance in mm above the well bottom to dispense at. Default is `extra_bottom_gap`.
    keep_tip : bool, optional
        If True, keep the tip on the pipette after completion. If False, drop tip.
        Default is False.
    
    Returns
    -------
    None
    
    Notes
    -----
    - Automatically picks up a tip if the pipette does not have one.
    - Uses `well_flow_rate` for aspiration and `sample_flow_rate` for dispensing.
    - Blow-out is performed at the source well top (-5mm) after each dispense.
    - Handles empty sample lists gracefully by converting to single-element list.
    
    Examples
    --------
    >>> apply_buffer(pipette_300, buffer_well, sample_chambers, 100)
    >>> apply_buffer(pipette_300, stain_well, single_sample, 50, keep_tip=True)
    """

    try:
        iter(samples)
    except TypeError:
        samples = [samples]
    
    if not pipette.has_tip: pipette.pick_up_tip()
    
    if(len(samples)==0):
        samples = [samples]

    for s in samples:
        pipette.aspirate(volume, sourceSolutionWell, rate=well_flow_rate)
        pipette.dispense(volume, s.bottom(dispense_bottom_gap), rate=sample_flow_rate)
        pipette.blow_out(sourceSolutionWell.top(-5))
    
    if not keep_tip: pipette.drop_tip()
    
def mix(pipette, sourceSolutionWell, volume, num_repeats, keep_tip = False):
    """
    Mix solution in a well by repeated aspiration and dispensing.
    
    Mixes a well by aspirating and dispensing the specified volume multiple times.
    Useful for homogenizing solutions prior to further operations.
    
    Parameters
    ----------
    pipette : Pipette
        The pipette instrument to use for mixing.
    sourceSolutionWell : Well
        The well to mix.
    volume : float
        Volume in microliters to aspirate and dispense during each mix cycle.
    num_repeats : int
        Number of times to repeat the aspiration-dispense cycle.
    keep_tip : bool, optional
        If True, keep the tip on the pipette after completion. If False, drop tip.
        Default is False.
    
    Returns
    -------
    None
    
    Notes
    -----
    - Automatically picks up a tip if the pipette does not have one.
    - Uses flow rate of 2 µL/s for both aspiration and dispensing.
    - This slow flow rate prevents splashing and ensures thorough mixing.
    
    Examples
    --------
    >>> mix(pipette_300, buffer_well, 150, 5)
    >>> mix(pipette_300, dilution_well, 100, 10, keep_tip=True)
    """

    if not pipette.has_tip: pipette.pick_up_tip()
    
    for i in range(0, num_repeats):
        pipette.aspirate(volume, sourceSolutionWell, rate=2)
        pipette.dispense(volume, sourceSolutionWell, rate=2)
    
    if not keep_tip: pipette.drop_tip()


def pierceSeal(pipette, target, keep_tip = False):
    """
    Pierce the foil seal of a well using the pipette tip.
    
    Moves the pipette tip to the top of a target well and then 5mm down to pierce
    any foil sealing the well. Useful for accessing sealed reagent reservoirs.
    
    Parameters
    ----------
    pipette : Pipette
        The pipette instrument to use for seal piercing.
    target : Well
        The well whose seal is to be pierced.
    keep_tip : bool, optional
        If True, keep the tip on the pipette after completion. If False, drop tip.
        Default is False.
    
    Returns
    -------
    None
    
    Notes
    -----
    - Automatically picks up a tip if the pipette does not have one.
    - Moves to well top first, then moves down 5mm to pierce seal.
    - Typically used before aspirating from sealed reagent bottles.
    
    Examples
    --------
    >>> pierceSeal(pipette_300, buffer_well)
    >>> pierceSeal(pipette_300, reagent_well, keep_tip=True)
    """

    if not pipette.has_tip: pipette.pick_up_tip()

    pipette.move_to(target.top())
    pipette.move_to(target.top(z=-5))

    if not keep_tip: pipette.drop_tip()


def dilute_and_apply_TSA(pipette, sourceSolutionWell, dilutant_buffer_well, samples, diluent_volume, application_volume, keep_tip = False, apply = True):
    """
    Dilute Tyramide oligo with TSA buffer reagent and optionally apply to samples.
    
    Dilutes a concentrated TSA solution by adding diluent and mixing, then optionally
    applies the diluted solution to sample chambers. This function is specifically
    designed for the PASTA staining protocol.
    
    Parameters
    ----------
    pipette : Pipette
        The pipette instrument to use for aspiration and dispensing.
    sourceSolutionWell : Well
        The well containing the concentrated TSA reagent to dilute.
    dilutant_buffer_well : Well
        The well containing the dilution buffer.
    samples : Well or list of Well
        Sample chamber(s) to apply diluted TSA to. Can be a single Well or an
        iterable of Wells.
    diluent_volume : float
        Volume in microliters of buffer to add to the TSA for dilution.
    application_volume : float
        Volume in microliters of diluted TSA to apply to each sample.
    keep_tip : bool, optional
        If True, keep the tip on the pipette after completion. If False, drop tip.
        Default is False.
    apply : bool, optional
        If True, apply the diluted TSA to samples. If False, only perform dilution
        and mixing. Default is True.
    
    Returns
    -------
    None
    
    Notes
    -----
    - Automatically picks up a tip if the pipette does not have one.
    - Mixes the diluted solution 10 times with half the diluent volume.
    - Application is split into two equal dispenses per sample.
    - Uses `well_flow_rate` for aspiration and `sample_flow_rate` for dispensing.
    - Handles empty sample lists gracefully by converting to single-element list.
    
    Examples
    --------
    >>> dilute_and_apply_TSA(pipette_300, tsa_well, buffer_well, samples, 40, 90)
    >>> dilute_and_apply_TSA(pipette_300, tsa_well, diluent_well, samples, 100, 50, apply=False)
    """

    try:
        iter(samples)
    except TypeError:
        samples = [samples]
    
    if not pipette.has_tip: pipette.pick_up_tip()
    
    if(len(samples)==0):
        samples = [samples]

    for s in samples:
    #Diluting Tyramide:
        pipette.aspirate(diluent_volume, dilutant_buffer_well, rate=well_flow_rate)
        pipette.dispense(diluent_volume, sourceSolutionWell, rate=well_flow_rate)
        mix(pipette, sourceSolutionWell, diluent_volume/2, 10, True)

    if apply:
        #Applying Tyramine to sample:
            pipette.aspirate(application_volume, sourceSolutionWell, rate=well_flow_rate)
            pipette.dispense(application_volume/2, s, rate=sample_flow_rate)
            pipette.dispense(application_volume/2, s, rate=sample_flow_rate)

    if not keep_tip: pipette.drop_tip()

def validate_cycle_sample_compatibility(protocol, num_samples, num_cycles):
    """Validate and pause if incompatible"""
    max_cycles_by_samples = {1: 32, 2: 16, 3: 8, 4: 8}
    
    if num_cycles > max_cycles_by_samples.get(num_samples, 0):
        protocol.pause(
            f"INCOMPATIBLE CONFIGURATION\n\n"
            f"Samples: {num_samples} | Cycles: {num_cycles}\n"
            f"Maximum: {max_cycles_by_samples[num_samples]} cycles\n\n"
            f"Fix the parameters and resume."
        )

########################## MAIN RUN FUNCTION #####################

# protocol run function. the part after the colon lets your editor know
# where to look for autocomplete suggestions
def run(protocol: protocol_api.ProtocolContext):

    ###### VALIDATION CHECK FOR CYCLE/SAMPLE NUMBER #####
    validate_cycle_sample_compatibility(protocol, num_samples, PASTA_cycles)

    ###########################LABWARE SETUP#################################
    temp_mod = protocol.load_module(module_name="temperature module gen2", location=labwarePositions.reagent_plate)
    black_96 = temp_mod.load_labware('parhelia_black_96')

    tiprack_300_1 = protocol.load_labware('opentrons_96_tiprack_300ul', labwarePositions.tiprack_300_1, 'tiprack 300ul')
    tiprack_300_2 = protocol.load_labware('opentrons_96_tiprack_300ul', labwarePositions.tiprack_300_2, 'tiprack 300ul')
    tiprack_300_3 = protocol.load_labware('opentrons_96_tiprack_300ul', labwarePositions.tiprack_300_3, 'tiprack 300ul')
    tiprack_300_4 = protocol.load_labware('opentrons_96_tiprack_300ul', labwarePositions.tiprack_300_4, 'tiprack 300ul')
    tiprack_300_5 = protocol.load_labware('opentrons_96_tiprack_300ul', labwarePositions.tiprack_300_5, 'tiprack 300ul')
    tiprack_300_6 = protocol.load_labware('opentrons_96_tiprack_300ul', labwarePositions.tiprack_300_6, 'tiprack 300ul')
    tiprack_300_7 = protocol.load_labware('opentrons_96_tiprack_300ul', labwarePositions.tiprack_300_7, 'tiprack 300ul')

    pipette_300 = protocol.load_instrument('p300_single_gen2' if pipette_300_GEN == 'GEN2' else 'p300_single', pipette_300_location, tip_racks = [tiprack_300_1, tiprack_300_2, tiprack_300_3, tiprack_300_4, tiprack_300_5, tiprack_300_6, tiprack_300_7])
    pipette_300.flow_rate.dispense = default_flow_rate
    pipette_300.flow_rate.aspirate = default_flow_rate

    par2 = protocol.load_labware(par2_type, labwarePositions.par2, 'PAR2')
    trough12_CODEX = protocol.load_labware('celltreat_12_reservoir_15000ul', labwarePositions.buffers_reservoir_1, 'CellTreat 12 Reservoir 15000 µL')
    trough12_Other = protocol.load_labware('celltreat_12_reservoir_15000ul', labwarePositions.buffers_reservoir_2, 'CellTreat 12 Reservoir 15000 µL')
   
    buffer_wells_CODEX = trough12_CODEX.wells_by_name()
    buffer_wells_Other = trough12_Other.wells_by_name()

    buffers = Object()

    sample_chambers = []

    for well in wellslist:
        sample_chambers.append(par2.wells_by_name()[well])

    ############ IN-LINE FUNCTIONS ##############
    def strip():
        protocol.comment("Initial Strip")

        mix(pipette_300, buffers.CODEX, 150, 5, keep_tip=True)
        washSamples(pipette_300, buffers.CODEX, sample_chambers, wash_volume, 2)

        mix(pipette_300, buffers.Strip, 150, 5, keep_tip=True)
        washSamples(pipette_300, buffers.Strip, sample_chambers, DMSO_volume, 3, DMSO_flow_rate, keep_tip=True)
        protocol.delay(minutes=3, msg = "Incubating Strip 1")
        washSamples(pipette_300, buffers.Strip, sample_chambers, DMSO_volume, 3, DMSO_flow_rate, keep_tip=True)
        protocol.delay(minutes=3, msg = "Incubating Strip 2")
        pipette_300.drop_tip()

        washSamples(pipette_300, buffers.CODEX, sample_chambers, wash_volume, 2, keep_tip=True)
        protocol.delay(seconds=30, msg = "Washing in 1XCODEX")
        washSamples(pipette_300, buffers.CODEX, sample_chambers, wash_volume, 2)
        protocol.delay(seconds=30, msg = "Washing in 1XCODEX")

    
    def create_cycle_config(num_samples, total_cycles):
        """
        Dynamically generate cycle configuration based on sample count.
        
        Parameters
        ----------
        num_samples : int
            Number of samples (1, 2, 3, or 4).
        total_cycles : int
            Total number of cycles to run.
        
        Returns
        -------
        dict
            Configuration dictionary keyed by cycle index (0-based).
        """
        if num_samples == 1:
            codex_interval = 4
            strip_interval = 8
        elif num_samples == 2:
            codex_interval = 2
            strip_interval = 4
        elif num_samples in [3, 4]:
            codex_interval = 1
            strip_interval = 2
        
        # Available wells in reservoirs
        codex_wells = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8']
        strip_wells = ['A1', 'A2', 'A3', 'A4']
        tbs_well = 'A12'
        
        config = {}
        codex_idx = 0
        strip_idx = 0
        
        for cycle_idx in range(total_cycles):
            config[cycle_idx] = {}
            pierce_list = []
            
            # Check if CODEX buffer changes this cycle
            if cycle_idx % codex_interval == 0:
                config[cycle_idx]['CODEX'] = codex_wells[codex_idx]
                codex_idx += 1
                pierce_list.append('CODEX')
            
            # Check if Strip buffer changes this cycle
            if cycle_idx % strip_interval == 0:
                config[cycle_idx]['Strip'] = strip_wells[strip_idx]
                strip_idx += 1
                pierce_list.append('Strip')
            
            # Add TBS and add it to pierce list on first cycle only
            if cycle_idx == 0:
                config[cycle_idx]['TBS'] = tbs_well
                pierce_list.insert(0, 'TBS')
            
            if pierce_list:
                config[cycle_idx]['pierce'] = pierce_list
        
        return config

    def update_cycle_buffers(cycle, config):
        """
        Update buffer references based on cycle configuration.
        
        Only updates and pierces buffers that are specified in the config
        for this cycle. Skips cycles with no config entries.
        """
        if cycle not in config:
            return  # No changes this cycle
        
        cycle_config = config[cycle]
        
        # Update buffers if specified
        if 'CODEX' in cycle_config:
            buffers.CODEX = buffer_wells_CODEX[cycle_config['CODEX']]
        if 'Strip' in cycle_config:
            buffers.Strip = buffer_wells_Other[cycle_config['Strip']]
        if 'TBS' in cycle_config:
            buffers.TBS = buffer_wells_CODEX[cycle_config['TBS']]
        
        # Pierce seals for this cycle's buffers
        if 'pierce' in cycle_config:
            pierce_items = cycle_config['pierce']
            for i, buffer_name in enumerate(pierce_items):
                keep_tip = i < len(pierce_items) - 1  # Drop tip on last pierce
                pierceSeal(pipette_300, getattr(buffers, buffer_name), keep_tip=keep_tip)

    


    #################PROTOCOL####################

    protocol.comment("Starting the PASTA protocol for samples:" + str(sample_chambers))

    temp_mod.set_temperature(celsius=4)

    for cycle in range(PASTA_cycles):
        protocol.comment("Starting Cycle: " + str(cycle+1) + "/" + str(PASTA_cycles))
        
        # Generate config on first cycle
        if cycle == 0:
            CYCLE_CONFIG = create_cycle_config(num_samples, PASTA_cycles)
        
        current_row = black_96.rows()[cycle % 8]
        cycle_jump = int(((cycle) // cycle_period) * cycle_offset)
        
        # Update buffers using generated config
        update_cycle_buffers(cycle, CYCLE_CONFIG)
        

        ## Initial Strip
        protocol.comment("Starting Strip")
        strip()

        #Staining oligo
        protocol.comment("Staining HRP Oligos")

        ##Pierce Seals
        for sample in range(len(sample_chambers)):
            well = (sample * sample_spacing) + cycle_jump
            pierceSeal(pipette_300, current_row[well], keep_tip=False)
        
        
        ##Mix wells
        for sample in range(len(sample_chambers)):
            well = (sample * sample_spacing) + cycle_jump
            mix(pipette_300, current_row[well], 50, 5, keep_tip=False)

        #Apply HRP oligos #1
        for sample in range(len(sample_chambers)):
            well = (sample * sample_spacing) + cycle_jump
            apply_buffer(pipette_300, current_row[well], sample_chambers[sample], 100, keep_tip=False)

        #Apply HRP oligos #2
        for sample in range(len(sample_chambers)):
            well = (sample * sample_spacing) + cycle_jump
            apply_buffer(pipette_300, current_row[well], sample_chambers[sample], 100, keep_tip=False)
        
        
        protocol.delay(minutes=10, msg = "Hybridizing oligos")

        #Wash
        protocol.comment("CODEX Wash 1")
        washSamples(pipette_300, buffers.CODEX, sample_chambers, wash_volume, 2, keep_tip=False)
        protocol.delay(minutes=1, msg="Washing")
        protocol.comment("CODEX Wash 2")
        washSamples(pipette_300, buffers.CODEX, sample_chambers, wash_volume, 2, keep_tip=True)
        protocol.delay(minutes=1, msg="Washing")
        protocol.comment("TBS Wash")
        mix(pipette_300, buffers.TBS, 150, 5, keep_tip=True)
        washSamples(pipette_300, buffers.TBS, sample_chambers, wash_volume, 2)
        protocol.delay(minutes=1, msg="Washing")


        #Applying Tyramide Oligo
        protocol.comment("TSA application")
        ##Pierce Seal
        for sample in range(len(sample_chambers)):
            Tyr_well = (sample * sample_spacing) + cycle_jump + 1
            Diluent_well = (sample * sample_spacing) + cycle_jump + 2
            pierceSeal(pipette_300, current_row[Tyr_well], keep_tip=False)
            pierceSeal(pipette_300, current_row[Diluent_well], keep_tip=False)
        
        ##Dilute Tyramide oligo
        for sample in range(len(sample_chambers)):
            Tyr_well = (sample * sample_spacing) + cycle_jump + 1
            Diluent_well = (sample * sample_spacing) + cycle_jump + 2
            sample_well_name = sample_chambers[sample].name  # Get 'A2', 'A3', etc.
            dilution_factor = Tyr_dilution_lib[cycle + 1][sample_well_name]  # +1 for cycle number
            Tyr_diluent_volume = 200 - (200 / dilution_factor)
            dilute_and_apply_TSA(pipette_300, current_row[Tyr_well], current_row[Diluent_well], sample_chambers[sample], Tyr_diluent_volume, 90, keep_tip=False, apply=False)
        
        ##Apply first TSA Batch
        for sample in range(len(sample_chambers)):
            Tyr_well = (sample * sample_spacing) + cycle_jump + 1
            apply_buffer(pipette_300, current_row[Tyr_well], sample_chambers[sample], 90, keep_tip=False)
        
        for i in range(0,3):
            protocol.delay(minutes=2, msg="Tyramide application")
            for sample in range(len(sample_chambers)):
                Tyr_well = (sample * sample_spacing) + cycle_jump + 1
                apply_buffer(pipette_300, current_row[Tyr_well], sample_chambers[sample], 25, keep_tip=False)

        protocol.delay(minutes=10, msg = "Final TSA Incubation")

        #Wash
        protocol.comment("CODEX Wash 1")
        washSamples(pipette_300, buffers.CODEX, sample_chambers, wash_volume, 2, keep_tip=False)
        protocol.delay(minutes=1, msg="Washing")
        protocol.comment("CODEX Wash 2")
        washSamples(pipette_300, buffers.CODEX, sample_chambers, wash_volume, 2, keep_tip=False)
        protocol.delay(minutes=1, msg="Washing")

    protocol.comment("Turning off the temperature module.")
    temp_mod.deactivate()

    protocol.comment("Final Strip")
    buffers.CODEX = buffer_wells_Other['A8']
    buffers.Strip = buffer_wells_Other['A7']
    strip()

    protocol.comment("Protocol Completed! Entering Hydration mode for " + str(hydration_time) + "hours.")

    #Hydration: Adding fresh CODEX buffer every 15 minutes
    HYDRATION_BUFFERS = {
        0: 'A9',
        6: 'A10',
        12: 'A11',
        18: 'A12'
    }

    for i in range(hydration_time * 4):
        cycle_hour = i // 4
        protocol.comment(f"Adding liquid as part of hydration cycle {i+1}/{hydration_time*4}")
        
        if cycle_hour in HYDRATION_BUFFERS:
            buffers.CODEX = buffer_wells_CODEX[HYDRATION_BUFFERS[cycle_hour]]
            pierceSeal(pipette_300, buffers.CODEX)
        
        mix(pipette_300, buffers.CODEX, 150, 5, keep_tip=True)
        washSamples(pipette_300, buffers.CODEX, sample_chambers, 100, 1, keep_tip=True)
        protocol.delay(minutes=15)