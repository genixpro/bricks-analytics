import React from 'react';
import {Col, Row, Panel, Alert, Checkbox} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {branch} from "recompose";
import ReactTable from 'react-table'
import _ from 'underscore';
import axios from "axios/index";
import {Stomp} from 'stompjs/lib/stomp.min';
import base64 from 'base-64';
import utf8 from 'utf8';

class CameraGrid extends React.Component {
    constructor(props) {
        super(props);

        this.state = {
            cameraImageCacheBuster: Date.now()
        }

    }

    /**
     * This function forces reload on all of the camera images
     */
    reloadCameraImage()
    {
        // Reload the camera image by changing the cache-buster query
        this.setState({cameraImageCacheBuster: Date.now()});
    }

    /**
     * Triggered when this component appears on the screen.
     */
    componentDidMount()
    {
        if (this.camera)
        {
            this.reloadCameraImage();
            this.updateInterval = setInterval(() => this.reloadCameraImage(), 2500);
        }
    }


    /**
     * Triggered when this component is being removed from the screen
     */
    componentWillUnmount()
    {
        if (this.updateInterval)
        {
            clearInterval(this.updateInterval);
        }
    }
    
    render() {
        return (
            <div className="camera-grid">
                <br/>
                <Row>
                    {
                        this.props.store.cameras &&
                        this.props.store.cameras.map((camera) =>
                            <Col md={3}>
                                <div className="panel b">
                                    <div className="panel-heading">
                                        <h4 className="m0">{camera.cameraId}</h4>
                                    </div>

                                    <div className="panel-body">
                                        {
                                            this.state.showCalibrationGrid
                                                ? <img id='live-image' className="live-image" src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/cameras/" + camera.cameraId + "/calibration?" + this.state.cameraImageCacheBuster} />
                                                : <img id='live-image' className="live-image" src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/cameras/" + camera.cameraId + "/image?" + this.state.cameraImageCacheBuster} />
                                        }
                                    </div>
                                </div>
                            </Col>
                        )
                    }
                </Row>
            </div>
        );
    }
}

export default withRouter(CameraGrid);


