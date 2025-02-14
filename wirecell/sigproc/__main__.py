#!/usr/bin/env python
'''
Export wirecell.sigproc functionality to a main Click program.
'''

import sys
import click

from wirecell import units

cmddef = dict(context_settings = dict(help_option_names=['-h', '--help']))

@click.group("sigproc", **cmddef)
@click.pass_context
def cli(ctx):
    '''
    Wire Cell Signal Processing Features
    '''

@cli.command("fr2npz")
@click.option("-g", "--gain", default=0.0, type=float,
                  help="Set gain in mV/fC.")
@click.option("-s", "--shaping", default=0.0, type=float,
                  help="Set shaping time in us.")
@click.argument("json-file")
@click.argument("npz-file")
def fr2npz(gain, shaping, json_file, npz_file):
    '''
    Convert field response file to numpy (.json or .json.bz2 to .npz)

    If gain and shaping are non zero then convolve each field response
    function with the corresponding electronics response function.

    Result holds a number of arrays and scalar values.

    Arrays:

        - resp[012] :: one 2D array for each plane.  A wire region is
          10 pixels wide.  Each row of pixels represents the average
          field response between the two original drift paths bounding
          the row.  The 2D array also makes explicit the
          flipped-symmetry that the original field response file
          leaves implicit.  The columns mark time.  Note, to make a
          per-wire sub-array of all impact rows #3 (counting from 0)
          you can use Numpy indexing like: dat['resp2'][3::10,:]

        - bincenters[012] :: the pitch location in mm of the row
          centers

        - pitches :: the nominal wire pitch for each plane as used in
          the Garfield simulation.

        - locations :: the locations along the drift direction of each
          of the planes.

        - eresp :: electronics response function, if gain/shaping given

        - espec :: the FFT of this, if gain/shaping given

    Scalar values:

        - origin :: in mm of where the drifts start in the same axis
          as the locations

        - tstart :: time when drift starts

        - period :: the sampling period in ns of the field response
          (ie, width of resp columns)

        - speed :: in mm/ns of the nominal electron drift speed used
          in the Garfield calculation.

        - gain : the passed in gain

        - shaping :: the passed in shaping time

    '''
    import wirecell.sigproc.response.persist as per
    import wirecell.sigproc.response.arrays as arrs
    import numpy
    fr = per.load(json_file)
    gain *= units.mV/units.fC
    shaping *= units.us
    dat = arrs.fr2arrays(fr, gain, shaping)
    numpy.savez(npz_file, **dat)


@cli.command("frzero")
@click.option("-n", "--number", default=0,
              help="Number of strip to keep, default keeps just zero strip")              
@click.option("-o", "--output",
              default="/dev/stdout",
              help="Output WCT file (.json or .json.bz2, def: stdout)")
@click.argument("infile")
@click.pass_context
def frzero(ctx, number, output, infile):
    '''
    Given a WCT FR file, make a new one with off-center wires zeroed.
    '''
    import wirecell.sigproc.response.persist as per
    import wirecell.sigproc.response.arrays as arrs
    fr = per.load(infile)
    for pr in fr.planes:
        for path in pr.paths:

            wire = int(path.pitchpos / pr.pitch)
            if abs(wire) <= number:
                print(f'keep wire: {wire}, pitch = {path.pitchpos} / {pr.pitch}')
                continue

            nc = len(path.current)
            for ind in range(nc):
                path.current[ind] = 0;
    per.dump(output, fr)

@cli.command("response-info")
@click.argument("json-file")
@click.pass_context
def response_info(ctx, json_file):
    '''
    Show some info about a field response file (.json or .json.bz2).
    '''
    import wirecell.sigproc.response.persist as per
    fr = per.load(json_file)
    print ("origin:%.2f cm, period:%.2f us, tstart:%.2f us, speed:%.2f mm/us, axis:(%.2f,%.2f,%.2f)" % \
           (fr.origin/units.cm, fr.period/units.us, fr.tstart/units.us, fr.speed/(units.mm/units.us), fr.axis[0],fr.axis[1],fr.axis[2]))
    for pr in fr.planes:
        print ("\tplane:%d, location:%.4fmm, pitch:%.4fmm" % \
               (pr.planeid, pr.location/units.mm, pr.pitch/units.mm))

@cli.command("convert-garfield")
@click.option("-o", "--origin", default="10.0*cm",
              help="Set drift origin (give units, eg '10*cm').")
@click.option("-s", "--speed", default="1.114*mm/us",
              help="Set nominal drift speed (give untis, eg '1.114*mm/us').")
@click.option("-n", "--normalization", default=0.0,
              help="Set normalization: 0:none, <0:electrons, >0:multiplicative scale.  def=0")
@click.option("-z", "--zero-wire-locs", default=[0.0,0.0,0.0], nargs=3, type=float,
              help="Set location of zero wires.  def: 0 0 0")
@click.option("-d", "--delay", default=0, type=int,
              help="Set additional delay of bins in the output field response.  def=0")
@click.argument("garfield-fileset")
@click.argument("wirecell-field-response-file")
@click.pass_context
def convert_garfield(ctx, origin, speed, normalization, zero_wire_locs,
                    delay, garfield_fileset, wirecell_field_response_file):
    '''
    Convert an archive of a Garfield fileset (zip, tar, tgz) into a
    Wire Cell field response file (.json with optional .gz or .bz2
    compression).
    '''
    import wirecell.sigproc.garfield as gar
    from wirecell.sigproc.response import rf1dtoschema
    import wirecell.sigproc.response.persist as per

    origin = eval(origin, units.__dict__)
    speed = eval(speed, units.__dict__)
    rflist = gar.load(garfield_fileset, normalization, zero_wire_locs, delay)
    fr = rf1dtoschema(rflist, origin, speed)
    per.dump(wirecell_field_response_file, fr)




@cli.command("plot-garfield-exhaustive")
@click.option("-n", "--normalization", default=0.0,
              help="Set normalization: 0:none, <0:electrons, >0:multiplicative scale.  def=0")
@click.option("-z", "--zero-wire-locs", default=[0.0,0.0,0.0], nargs=3, type=float,
              help="Set location of zero wires.  def: 0 0 0")
@click.argument("garfield-fileset")
@click.argument("pdffile")
@click.pass_context
def plot_garfield_exhaustive(ctx, normalization, zero_wire_locs,
                                 garfield_fileset, pdffile):
    '''
    Plot all the Garfield current responses.
    '''
    import wirecell.sigproc.garfield as gar
    dat = gar.load(garfield_fileset, normalization, zero_wire_locs)
    import wirecell.sigproc.plots as plots
    plots.garfield_exhaustive(dat, pdffile)

@cli.command("plot-garfield-track-response")
@click.option("-g", "--gain", default=-14.0,
                  help="Set gain in mV/fC.")
@click.option("-s", "--shaping", default=2.0,
                  help="Set shaping time in us.")
@click.option("-t", "--tick", default=0.5,
                  help="Set tick time in us (0.1 is good for no shaping).")
@click.option("-p", "--tick-padding", default=0,
                  help="Number of ticks of zero ADC to pre-pad the plots.")
@click.option("-e", "--electrons", default=13300,
                help="Set normalization in units of electron charge.")
@click.option("--elec-type", default="cold", type=str,
                  help="Set electronics type [cold | warm] (def: cold).")
@click.option("-a", "--adc-gain", default=1.2,
                  help="Set ADC gain (unitless).")
@click.option("--adc-voltage", default=2.0,
                  help="Set ADC voltage range in Volt.")
@click.option("--adc-resolution", default=12,
                  help="Set ADC resolution in bits.")
@click.option("-n", "--normalization", default=-1,
                  help="Set normalization: 0:none, <0:electrons, >0:multiplicative scale.  def=-1")
@click.option("-z", "--zero-wire-locs", default=[0.0, 0.0, 0.0], nargs=3, type=float,
              help="Set location of zero wires.  def: 0 0 0")
@click.option("--ymin", default=-40.0,
                  help="Set Y min")
@click.option("--ymax", default=60.0,
                  help="Set Y max")
@click.option("--regions", default=0, type=int,
                  help="Set how many wire regions to use, default to all")
@click.option("--dump-data", default="", type=str,
                  help="Dump the plotted data in format given by extension (.json, .txt or .npz/.npy)")
@click.argument("garfield-fileset")
@click.argument("pdffile")
@click.pass_context
def plot_garfield_track_response(ctx, gain, shaping, tick, tick_padding, electrons,
                                     elec_type, adc_gain, adc_voltage, adc_resolution,
                                     normalization, zero_wire_locs,
                                     ymin, ymax, regions,
                                     dump_data,
                                     garfield_fileset, pdffile):
    '''
    Plot Garfield response assuming a perpendicular track.

    Note, defaults are chosen to reproduce the "ADC Waveform with 2D
    MicroBooNE Wire Plane Model" plot for the MicroBooNE noise paper.
    '''
    import wirecell.sigproc.garfield as gar
    import wirecell.sigproc.response as res
    import wirecell.sigproc.plots as plots

    gain *= units.mV/units.fC
    shaping *= units.us
    tick *= units.us
    electrons *= units.eplus

    adc_gain *= 1.0                       # unitless
    adc_voltage *= units.volt
    adc_resolution = 1<<adc_resolution
    adc_per_voltage = adc_gain*adc_resolution/adc_voltage

    dat = gar.load(garfield_fileset, normalization, zero_wire_locs)

    if regions:
        print ("Limiting to %d regions" % regions)
        dat = [r for r in dat if abs(r.region) in range(regions)]

    uvw = res.line(dat, electrons)

    detector = ""
    if "ub_" in garfield_fileset:
        detector = "MicroBooNE"
    if "dune_" in garfield_fileset:
        detector = "DUNE"
    print ('Using detector hints: "%s"' % detector)

    nwires = len(set([abs(r.region) for r in dat])) - 1
    #msg = "%d electrons, +/- %d wires" % (electrons, nwires)
    msg=""

    fig,data = plots.plot_digitized_line(uvw, gain, shaping,
                                         tick = tick,
                                         elec_type = elec_type,
                                         adc_per_voltage = adc_per_voltage,
                                         detector = detector,
                                         ymin=ymin, ymax=ymax, msg=msg,
                                         tick_padding=tick_padding)
    print ("plotting to %s" % pdffile)
    fig.savefig(pdffile)

    if dump_data:
        print ("dumping data to %s" % dump_data)

        if dump_data.endswith(".npz"):
            import numpy
            numpy.savez(dump_data, data);
        if dump_data.endswith(".npy"):
            import numpy
            numpy.save(dump_data, data);
        if dump_data.endswith(".txt"):
            with open(dump_data,"wt") as fp:
                for line in data:
                    line = '\t'.join(map(str, line))
                    fp.write(line+'\n')
        if dump_data.endswith(".json"):
            import json
            open(dump_data,"wt").write(json.dumps(data.tolist(), indent=4))


@cli.command("plot-response-compare-waveforms")
@click.option("-p", "--plane", default=0,
              help="Plane")
@click.option("--irange", default='0',
              help="Impact range as comma separated integers")
@click.option("--trange", default='0,70',
              help="Set time range in us as comma pair. def: 0,70")
@click.argument("responsefile1")
@click.argument("responsefile2")
@click.argument("outfile")
@click.pass_context
def plot_response_compare_waveforms(ctx, plane, irange, trange, responsefile1, responsefile2, outfile):
    '''
    Plot common response waveforms from two sets
    '''
    import wirecell.sigproc.response.persist as per
    import wirecell.sigproc.response.plots as plots

    irange = list(map(int, irange.split(',')))
    trange = list(map(int, trange.split(',')))

    colors = ["red","blue"]
    styles = ["solid","solid"]

    import matplotlib.pyplot as plt
    import numpy
    def plot_paths(rfile, n):
        fr = per.load(rfile)
        pr = fr.planes[plane]
        print(f'{colors[n]} {rfile}: plane={plane} {len(pr.paths)} paths:')
        for ind in irange:
            path = pr.paths[ind]
            tot_q = numpy.sum(path.current)*fr.period
            dt_us = fr.period/units.us
            tot_es = tot_q / units.eplus
            print (f'\t{ind}: {path.pitchpos:f}: {len(path.current)} samples, dt={dt_us:.3f} us, tot={tot_es:.3f} electrons')
            plt.gca().set_xlim(*trange)

            times = plots.time_linspace(fr, plane)

            plt.plot(times/units.us, path.current, color=colors[n], linestyle=styles[n])
        
    plot_paths(responsefile1,0)
    plot_paths(responsefile2,1)
    plt.savefig(outfile)




@cli.command("plot-response")
@click.option("--region", default=None, type=float,
              help="Set a region to demark as 'electrode 0'. def: none")
@click.option("--trange", default='0,70',
              help="Set time range in us as comma pair. def: 0,70")
@click.option("--title", default='Response:',
              help="An initial distinguishing title")
@click.option("--reflect/--no-reflect", default=True,
              help="Apply symmetry reflection")
@click.argument("responsefile")
@click.argument("outfile")
@click.pass_context
def plot_response(ctx, responsefile, outfile, region, trange, title, reflect):
    '''
    Plot per plane responses.
    '''
    import wirecell.sigproc.response.persist as per
    import wirecell.sigproc.response.plots as plots

    trange = list(map(int, trange.split(',')))
    fr = per.load(responsefile)
    plots.plot_planes(fr, outfile, trange, region, reflect, title)


@cli.command("plot-response-conductors")
@click.option("--trange", default='0,70',
              help="Set time range in us as comma pair. def: 0,70")
@click.option("--title", default='Response:',
              help="An initial distinguishing title")
@click.option("--log10/--no-log10", default=False,
              help="Use 'signed log10' else linear scale")
@click.option("--regions", default=None,
              help="Comma separated list of regions, default is all")
@click.argument("responsefile")
@click.argument("outfile")
@click.pass_context
def plot_response(ctx, trange, title, log10, regions, responsefile, outfile):
    '''
    Plot per-conductor (wire/strip) respnonses.
    '''
    import wirecell.sigproc.response.persist as per
    import wirecell.sigproc.response.plots as plots

    trange = list(map(int, trange.split(',')))
    if regions:
        regions = list(map(int, regions.split(',')))
    fr = per.load(responsefile)
    plots.plot_conductors(fr, outfile, trange, title, log10, regions)



@cli.command("plot-spectra")
@click.argument("responsefile")
@click.argument("outfile")
@click.pass_context
def plot_spectra(ctx, responsefile, outfile):
    '''
    Plot per plane response spectra.
    '''
    import wirecell.sigproc.response.persist as per
    import wirecell.sigproc.response.plots as plots

    fr = per.load(responsefile)
    plots.plot_specs(fr, outfile)


@cli.command("plot-electronics-response")
@click.option("-g", "--gain", default=14.0,
              help="Set gain in mV/fC.")
@click.option("-s", "--shaping", default=2.0,
              help="Set shaping time in us.")
@click.option("-t", "--tick", default=0.5,
              help="Set tick time in us (0.1 is good for no shaping).")
@click.option("-e", "--electype", default="cold",
              help="Set electronics type [cold | warm] (def: cold).")
@click.argument("plotfile")
@click.pass_context
def plot_electronics_response(ctx, gain, shaping, tick, electype, plotfile):
    '''
    Plot the electronics response function.
    '''
    gain *= units.mV/units.fC
    shaping *= units.us
    tick *= units.us
    import wirecell.sigproc.plots as plots
    fig = plots.one_electronics(gain, shaping, tick, electype)
    fig.savefig(plotfile)


@cli.command("convert-noise-spectra")
@click.option("-f","--format", default="microboonev1",
                  help="Format of input file")
@click.argument("inputfile")
@click.argument("outputfile")
@click.pass_context
def convert_noise_spectra(ctx, format, inputfile, outputfile):
    '''
    Convert an file of noise spectra in some external format into WCT format.
    '''
    loader = None
    if format == "microboonev1":
        from wirecell.sigproc.noise.microboone import load_noise_spectra_v1
        loader = load_noise_spectra_v1
    elif format == "icarusv1-incoherent":
        from wirecell.sigproc.noise.icarus import load_noise_spectra
        loader = load_noise_spectra
    elif format == "icarusv1-coherent":
        from wirecell.sigproc.noise.icarus import load_coherent_noise_spectra
        loader = load_coherent_noise_spectra

    if not loader:
        click.echo('Unknown format: "%s"' % format)
        sys.exit(1)

    spectra = loader(inputfile)

    from wirecell.sigproc.noise import persist
    persist.dump(outputfile, spectra)

@cli.command("convert-electronics-response")
@click.argument("inputfile")
@click.argument("outputfile")
@click.pass_context
def convert_noise_spectra(ctx, inputfile, outputfile):
    '''
    Convert a table of electronics response function in some external format into WCT format.
    '''
    from wirecell.sigproc.response import load_text_electronics_response
    loader = load_text_electronics_response
    if not loader:
        click.echo('Unknown format: "%s"' % format)
        sys.exit(1)

    elecresp = loader(inputfile)

    from wirecell.sigproc.response import persist
    persist.dump(outputfile, elecresp)

from wirecell.util.cli import jsonnet_loader
from wirecell.util import jsio
@cli.command("plot-noise-spectra")
@jsonnet_loader("spectra")
@click.argument("plotfile")
@click.pass_context
def plot_noise_spectra(ctx, spectra, plotfile, **kwds):
    '''
    Plot contents of a WCT noise spectra file such as produced by
    the convert-noise-spectra subcommand or a NoiseModeler.
    '''
    from wirecell.sigproc.noise import plots
    plots.plot_many(spectra, plotfile)



@cli.command("channel-responses")
@click.option("-t","--tscale", default="0.5*us", type=str,
                  help="Scale of time axis in the histogram.")
@click.option("-s","--scale", default="1e-9*0.5/1.13312", type=str,
                  help="Scale applied to the samples.")
@click.option("-n","--name", default="pResponseVsCh",
                  help="Data name (eg, the TH2D name if using 'hist' schema")
@click.argument("infile")
@click.argument("outfile")
@click.pass_context
def channel_responses(ctx, tscale, scale, name, infile, outfile):
    '''Produce the per-channel calibrated response JSON file from a TH2D
    of the given name in the input ROOT file provided by the analysis.

    - tscale :: a number to multiply to the time axis of the histogram
      in order to bring the result into the WCT system of units.  It
      may be expressed as a string of an algebraic expression which
      includes symbols, eg "0.5*us".

    - scale :: a number multiplied to all samples in the histogram in
      order to make the sample value a unitless relative measure.  It
      may be expressed as a string of an algebraic expression which
      includes symbols, eg "0.5*us". For uBoone's initial
      20171006_responseWaveforms.root the appropriate scale is
      1e-9*0.5/1.13312 = 4.41267e-10
    '''
    import json
    import ROOT
    import numpy
    from root_numpy import hist2array

    tscale = eval(tscale, units.__dict__)
    scale = eval(scale, units.__dict__)

    tf = ROOT.TFile.Open(str(infile))
    assert(tf)
    h = tf.Get(str(name))
    if not h:
        click.echo('Failed to get histogram "%s" from %s' % (name, infile))
        sys.exit(1)

    arr,edges = hist2array(h, return_edges=True)

    arr *= scale
    tedges = edges[1]
    t0,t1 = tscale*(tedges[0:2])
    tick = t1-t0

    nchans, nticks = arr.shape
    channels = list()
    for ch in range(nchans):
        # reduce down to ~32 bit float precision to save file space
        res = [float("%.6g"%x) for x in arr[ch,:].tolist()]
        one = [ch, res]
        channels.append(one)

    dat = dict(tick=tick, t0=t0, channels=channels)

    jtext = json.dumps(dat, indent=4)
    if outfile.endswith(".json.bz2"):
        import bz2
        bz2.BZ2File(outfile, 'w').write(jtext)
        return
    if outfile.endswith(".json.gz"):
        import gzip
        gzip.open(outfile, 'wb').write(jtext) # wb?
        return

    open(outfile, 'w').write(jtext)
    return


def main():
    cli(obj=dict())

if '__main__' == __name__:
    main()
